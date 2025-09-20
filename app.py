import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import google.generativeai as genai
import fitz  # PyMuPDF
import json
import logging

# Set logging level
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()

# Configure Google API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-pro-latest')

app = Flask(__name__)

# Configure CORS to allow requests from your frontend's domain
# Replace 'https://ai-pitchdeck-frontend.onrender.com' with the actual URL
# of your deployed frontend. You can also use a wildcard '*' for
# development, but it's less secure.
CORS(app, origins=["https://ai-pitchdeck-frontend.onrender.com"])

@app.route('/ask', methods=['POST'])
def handle_ask():
    logging.debug("Received a request to /ask")
    if 'file' not in request.files:
        logging.error("No file part in the request")
        return jsonify({'detail': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        logging.error("No selected file")
        return jsonify({'detail': 'No selected file'}), 400

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join("/tmp", filename)
        file.save(filepath)
        logging.debug(f"File saved to {filepath}")

        try:
            doc = fitz.open(filepath)
            text_content = ""
            for page in doc:
                text_content += page.get_text()
            logging.debug(f"Extracted text content of size {len(text_content)} characters.")

            prompt_parts = [
                "You are an AI Startup Analyst. I will provide you with a pitch deck in text format. Your task is to analyze it and generate a detailed investment memo. The memo should cover the following sections:",
                "1. **Executive Summary:** A brief, high-level overview of the startup, its business model, and the investment opportunity.",
                "2. **Team:** An analysis of the founding team's experience and expertise.",
                "3. **Problem & Solution:** A clear description of the problem the startup is solving and its proposed solution.",
                "4. **Market Analysis:** An assessment of the target market size, growth potential, and competitive landscape.",
                "5. **Product/Service:** A review of the product or service, its key features, and unique selling propositions.",
                "6. **Business Model & Traction:** Details on how the startup generates revenue and any key metrics or milestones achieved (e.g., users, revenue, growth rates).",
                "7. **Financials (if available):** An overview of the financial health, including revenue, expenses, and fundraising history.",
                "8. **Investment Ask & Use of Funds:** The amount of capital being raised and how it will be used.",
                "9. **Risks:** An identification of potential risks and challenges.",
                "10. **Conclusion & Recommendation:** A final recommendation on whether to invest, supported by a summary of the key findings.",
                "---",
                "Pitch Deck Text:",
                text_content,
                "---",
                "Please format your response using Markdown for easy readability. Do not include any filler text before or after the investment memo itself. Start directly with the memo."
            ]
            
            response = model.generate_content(prompt_parts)
            
            # The API returns markdown content within a 'text' field.
            memo_markdown = response.text
            
            logging.debug("Successfully generated investment memo.")
            
            return jsonify({'markdown': memo_markdown}), 200

        except Exception as e:
            logging.error(f"An error occurred: {e}", exc_info=True)
            return jsonify({'detail': f'An internal error occurred during analysis: {e}'}), 500
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
                logging.debug(f"Temporary file {filepath} removed.")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
