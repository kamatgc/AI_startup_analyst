from flask import Flask, request, jsonify
from flask_cors import CORS
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
import google.generativeai as genai
import os
import io

app = Flask(__name__)
# Enable CORS for all routes and all origins
CORS(app)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Function to extract text and images from a PDF
def extract_content_from_pdf(pdf_path):
    """
    Extracts content from a PDF file.

    Returns a list of image objects and a combined string of text from all pages.
    """
    images = convert_from_path(pdf_path)
    # Placeholder for text extraction - will be implemented if required
    text = "Text content is not currently extracted."
    return images, text

# Function to generate an investment memo
def generate_investment_memo(images, text_content):
    """
    Generates a detailed investment memo using Google's Gemini API.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        system_prompt = (
            "You are a highly experienced and detailed venture capital analyst. Your task is to analyze a startup pitch deck "
            "and create a professional, comprehensive, and detailed investment memo. The pitch deck is provided as a series of images "
            "and some text content. Your memo should be structured with the following key sections:\n\n"
            "1. Executive Summary: A concise overview of the company, its mission, and the investment opportunity.\n"
            "2. Company & Product: Detailed analysis of the startup's core business, product, and technology.\n"
            "3. Market Opportunity: Assessment of the market size, target audience, and industry trends.\n"
            "4. Business Model: Explanation of how the company generates revenue, its pricing strategy, and unit economics.\n"
            "5. Team: Evaluation of the founding team's experience, expertise, and ability to execute.\n"
            "6. Competitive Landscape: Analysis of key competitors, the company's competitive advantages, and its defensibility.\n"
            "7. Financials: Summary of key financial metrics, funding history, and projections.\n"
            "8. Investment Recommendation: Your final recommendation on whether to invest, supported by key rationale and potential risks.\n\n"
            "Ensure the memo is professional, well-structured, and provides deep insights for a potential investor."
        )
        
        # Prepare the parts for the model
        parts = [
            {"text": system_prompt},
            *images,
            {"text": f"Here is the pitch deck's text content: {text_content}"}
        ]

        # Generate content with safety settings
        response = model.generate_content(
            contents=parts,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        return response.text
    except Exception as e:
        print(f"Error in generating content: {e}")
        return f"An error occurred during memo generation: {str(e)}"

@app.route("/")
def home():
    """Welcome route for the web browser."""
    return "<h1>AI Pitch Deck Analyzer API is Live!</h1><p>Send a POST request to /ask with a PDF file.</p>"

@app.route("/ask", methods=["POST"])
def ask():
    """Handles the PDF upload and analysis."""
    print("Received POST request to /ask. Starting analysis...")
    if 'pdf_file' not in request.json:
        return jsonify({"error": "No PDF file found in request"}), 400

    base64_pdf = request.json['pdf_file']
    
    # Decode the base64 PDF
    pdf_data = io.BytesIO(base64_pdf.encode('utf-8'))

    # Save the PDF temporarily to be processed by pdf2image
    try:
        temp_pdf_path = "temp_pitchdeck.pdf"
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_data.getbuffer())

        # Extract images and text
        images, text_content = extract_content_from_pdf(temp_pdf_path)

        # Generate investment memo
        investment_memo = generate_investment_memo(images, text_content)

        # Clean up the temporary file
        os.remove(temp_pdf_path)

        return jsonify({"investment_memo": investment_memo})

    except Exception as e:
        print(f"Error processing PDF: {e}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
