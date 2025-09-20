import os
import io
import pathlib
import json

import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter

load_dotenv()
app = Flask(__name__)
CORS(app)

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel('gemini-1.5-flash')

# Define safety settings to be passed directly to the model
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    },
]

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Server is up and running!"})


@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    question = data.get('question')
    print(f"Received question: {question}")
    
    if not question:
        return jsonify({"error": "Question not provided"}), 400

    try:
        response = model.generate_content(
            question,
            safety_settings=safety_settings
        )
        print(f"Model response: {response.text}")
        return jsonify({"answer": response.text})
    except Exception as e:
        print(f"Error during content generation: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        
        if file and file.filename.endswith('.pdf'):
            # It's a PDF, so we use Google's PDF processing
            pdf_bytes = file.read()
            pdf_file = genai.upload_file(pdf_bytes, mime_type='application/pdf')
            
            prompt = """
            Analyze this pitch deck. Provide a concise, single-paragraph summary of the key findings.
            Focus on the following key areas and provide your analysis as a JSON object:
            1.  **Executive Summary:** A brief, high-level overview.
            2.  **Problem:** Identify the core problem the company is trying to solve.
            3.  **Solution:** Explain the proposed solution.
            4.  **Target Market:** Describe the intended customer base.
            5.  **Business Model:** Explain how the company plans to make money.
            6.  **Traction & Milestones:** Highlight any significant achievements or progress.
            7.  **Team:** Comment on the team's expertise and background.
            8.  **Competition:** Identify key competitors and the company's competitive advantage.
            9.  **Financials:** Summarize any financial projections or funding requests.
            10. **Overall Rating:** Provide a rating from 1 to 10 (10 being best) and a justification for the rating.

            The final output MUST be a valid JSON object. Do not include any text outside of the JSON.
            """
            
            response = model.generate_content(
                [prompt, pdf_file],
                safety_settings=safety_settings
            )
            
            try:
                # Assuming the response text is a valid JSON string
                analysis_data = json.loads(response.text)
            except json.JSONDecodeError:
                return jsonify({'error': 'Model did not return valid JSON. Please try again.'}), 500
            
            return jsonify(analysis_data)

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    data = request.json
    analysis_data = data.get('analysis')

    if not analysis_data:
        return jsonify({'error': 'No analysis data provided'}), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Pitchdeck Analysis Report", styles['Title']))
    story.append(Spacer(1, 0.2 * inch))

    for section, content in analysis_data.items():
        if section.lower() == 'overall rating':
            # Handle rating with special formatting
            title_text = f"<b>{section.replace('_', ' ').title()}</b>"
            story.append(Paragraph(title_text, styles['h2']))
            rating_text = f"Rating: {content['rating']}/10"
            justification_text = f"Justification: {content['justification']}"
            story.append(Paragraph(rating_text, styles['Normal']))
            story.append(Paragraph(justification_text, styles['Normal']))
        else:
            title_text = f"<b>{section.replace('_', ' ').title()}</b>"
            story.append(Paragraph(title_text, styles['h2']))
            story.append(Paragraph(content, styles['Normal']))
            
        story.append(Spacer(1, 0.2 * inch))
    
    doc.build(story)
    buffer.seek(0)
    
    return buffer.getvalue(), 200, {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename=analysis_report.pdf'
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=True)
