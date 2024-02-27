import base64
import io
from docx import Document
import dash
from dash import dcc, html, Input, Output, State  # Ensure all components are imported correctly
from dash.exceptions import PreventUpdate  # Confirm this import for handling no-updates condition
import openai
import os

openai_api_key = os.getenv("OPENAI_API_KEY")


app = dash.Dash(__name__)
server = app.server
# Custom CSS styles for nicer aesthetics
app.layout = html.Div([
    dcc.Upload(
        id='upload-document',
        children=html.Div(['Drag and Drop or ', html.A('Select Files')]),
        style={
            'width': '100%', 'height': '60px', 'lineHeight': '60px',
            'borderWidth': '2px', 'borderStyle': 'dashed', 'borderRadius': '10px',
            'textAlign': 'center', 'margin': '20px', 'fontSize': '20px'
        },
        multiple=False
    ),
    html.Div([
        dcc.Input(id='doc-type', type='text', placeholder='Document Type (e.g., legal, academic)',
                  style={'width': '100%', 'margin': '5px 0', 'padding': '10px'}),
        dcc.Input(id='source-lang', type='text', placeholder='Source Language (e.g., Spanish)',
                  style={'width': '100%', 'margin': '5px 0', 'padding': '10px'}),
        dcc.Input(id='target-lang', type='text', placeholder='Target Language (e.g., English)',
                  style={'width': '100%', 'margin': '5px 0', 'padding': '10px'}),
        dcc.Textarea(id='specific-instructions', placeholder='Specific translation instructions or keywords',
                     style={'width': '100%', 'height': 150, 'margin': '5px 0', 'padding': '10px'}),
    ], style={'margin': '10px 0'}),
    html.Div(id='uploaded-file-name'),
    html.Button('Translate Document', id='translate-button', n_clicks=0,
                style={'background-color': '#007bff', 'color': 'white', 'padding': '10px 24px', 'fontSize': '20px', 'borderRadius': '5px'}),
    html.Div(id='output-container', children=[
        dcc.Loading(
            id="loading",
            type="default",
            children=html.Div(id="output-download-link")
        )
    ])
], style={'fontFamily': 'Arial, sans-serif', 'padding': '20px'})

def translate(text, doc_type, source_lang, target_lang, specific_instructions):
    # Generate the custom prompt based on user input
    custom_prompt = f"You are a professional translator with expertise in translating {doc_type} texts from {source_lang} to {target_lang}. {specific_instructions} Now, translate the following:"
    
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "system", "content": custom_prompt},
                {"role": "user", "content": text}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error during translation: {str(e)}")
        return None


def process_document(contents, doc_type, source_lang, target_lang, specific_instructions):
    # Decode the base64 content and read the document
    decoded_document = base64.b64decode(contents.split(',')[1])
    document_stream = io.BytesIO(decoded_document)
    doc = Document(document_stream)

    paragraphs = [paragraph for paragraph in doc.paragraphs if paragraph.text.strip() != ""]
    paragraph_count = 0

    # Process the paragraphs in pairs with custom instructions
    while paragraph_count < len(paragraphs):
        combined_text = ''
        if paragraph_count + 1 < len(paragraphs):  # If there is at least one more paragraph
            combined_text = paragraphs[paragraph_count].text + "\n\n" + paragraphs[paragraph_count + 1].text
            translated_text = translate(combined_text, doc_type, source_lang, target_lang, specific_instructions)
            translated_paragraphs = translated_text.split("\n\n")
            if len(translated_paragraphs) == 2:
                paragraphs[paragraph_count].text = translated_paragraphs[0]
                paragraphs[paragraph_count + 1].text = translated_paragraphs[1]
            paragraph_count += 2
        else:  # If there's a single paragraph left
            combined_text = paragraphs[paragraph_count].text
            translated_text = translate(combined_text, doc_type, source_lang, target_lang, specific_instructions)
            paragraphs[paragraph_count].text = translated_text
            paragraph_count += 1

    # Saving the translated document into a BytesIO object instead of directly to disk
    output_io = io.BytesIO()
    doc.save(output_io)
    output_io.seek(0)
    return output_io


@app.callback(
    [Output('output-download-link', 'children'),
     Output('uploaded-file-name', 'children')],
    [Input('translate-button', 'n_clicks'),
     Input('upload-document', 'contents')],  # Listening for changes in contents here
    [State('upload-document', 'filename'),
     State('doc-type', 'value'),
     State('source-lang', 'value'),
     State('target-lang', 'value'),
     State('specific-instructions', 'value')]
)
def update_output(n_clicks, contents, filename, doc_type, source_lang, target_lang, specific_instructions):
    ctx = dash.callback_context

    if not ctx.triggered or contents is None:
        # This will prevent the callback from firing before any content is uploaded
        raise PreventUpdate

    input_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if input_id == 'upload-document':
        uploaded_file_message = f"Uploaded file: {filename}" if filename else "No file uploaded."
        # If the upload-document triggered this callback, we should not proceed to process the document yet
        return None, uploaded_file_message

    # The below code now assumes contents is defined and proceeds if the button was clicked
    try:
        translated_doc_io = process_document(contents, doc_type, source_lang, target_lang, specific_instructions)
        translated_doc_b64 = base64.b64encode(translated_doc_io.read()).decode('utf-8')
        download_link = html.A('Download Translated Document',
                               href=f"data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{translated_doc_b64}",
                               download=f"translated_{filename}")
        return download_link, f"Uploaded file: {filename}"
    except Exception as e:
        return html.Div(['There was an error processing this file. ', str(e)]), f"Uploaded file: {filename}"



if __name__ == '__main__':
    app.run_server(debug=False)
