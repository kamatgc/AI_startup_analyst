import os
import io
import time
import requests
import google.generativeai as genai
from flask import Flask, jsonify, request
from flask_cors import CORS
from PyPDF2 import PdfReader
from google.api_core.exceptions import ResourceExhausted

app = Flask(__name__)
CORS(app)

# Set up the Gemini API key from environment variables
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable not set")

genai.configure(api_key=api_key)

# We are switching to the 'gemini-2.5-flash-preview-05-20' model for better free-tier performance.
# This model is faster and has a higher rate limit, which is ideal for an MVP.
model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')

def extract_text_from_pdf(pdf_file):
    """
    Extracts text from a PDF file.
    """
    try:
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None

def analyze_pitch_deck(text_content):
    """
    Analyzes the pitch deck text content using the Gemini API.
    """
    # Define the prompt for the Gemini API.
    prompt_text = (
        "You are an expert AI startup analyst. Your task is to analyze a pitch deck "
        "and generate a concise, detailed investment memo. The memo should be "
        "structured clearly with the following sections:\n\n"
        "1. Executive Summary: A brief, high-level overview of the company, "
        "its purpose, and the investment opportunity.\n"
        "2. Team: A summary of the founding team's experience and qualifications.\n"
        "3. Problem: The problem the company is solving.\n"
        "4. Solution: The product or service offered by the company.\n"
        "5. Market Opportunity: The total addressable market (TAM) and the "
        "potential for growth.\n"
        "6. Business Model: How the company makes money.\n"
        "7. Traction: Any key milestones, user growth, revenue, or partnerships.\n"
        "8. Competition: A brief analysis of competitors and the company's "
        "competitive advantage.\n\n"
        "Here is the text extracted from the pitch deck:\n\n"
        f"{text_content}"
    )

    prompt_parts = [
        {"text": prompt_text}
    ]

    # Implement a retry mechanism with exponential backoff for a more robust application.
    # This will help prevent ResourceExhausted errors (429) that occur in the free tier.
    max_retries = 5
    base_delay = 1 # seconds
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt_parts)
            # Handle empty response
            if response and response.text:
                return response.text
            else:
                return "Error: Empty response from model."
        except ResourceExhausted as e:
            delay = base_delay * (2 ** attempt)
            print(f"ResourceExhausted error (429) on attempt {attempt + 1}. Retrying in {delay} seconds.")
            time.sleep(delay)
            if attempt == max_retries - 1:
                return f"Error: Failed to get a response after {max_retries} attempts due to quota limits."
        except Exception as e:
            print(f"An error occurred: {e}")
            return f"An unexpected error occurred: {e}"
    
    return "Error: Failed to get a response after multiple retries."


@app.route("/")
def home():
    """
    Simple route to confirm the Flask server is running.
    """
    return "AI Pitch Deck Analyst Backend is running!"

@app.route("/ask", methods=["POST"])
def handle_ask():
    """
    Handles the POST request for analyzing a pitch deck.
    """
    print("Received a request to /ask")
    # Check if 'pdf_file' is in the request files
    if 'pdf_file' not in request.files:
        print("Error: No file part in the request.")
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['pdf_file']

    # Check if a file was selected
    if file.filename == '':
        print("Error: No selected file.")
        return jsonify({"error": "No selected file"}), 400
    
    # Check if the file has content
    if file.content_length == 0:
        print("Error: Empty file uploaded.")
        return jsonify({"error": "Empty file uploaded"}), 400

    print(f"Received file: {file.filename}, Content-Length: {file.content_length}")
    
    try:
        # Create a BytesIO object from the file data
        file_stream = io.BytesIO(file.read())
        
        # Extract text from the PDF directly from the stream
        text_content = extract_text_from_pdf(file_stream)
        file_stream.close() # Close the stream

        if text_content:
            print(f"Extracted text content of size {len(text_content)} characters.")
            investment_memo = analyze_pitch_deck(text_content)
            return jsonify({"response": investment_memo})
        else:
            print("Failed to extract text from PDF.")
            return jsonify({"error": "Failed to extract text from PDF."}), 500

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500

    return jsonify({"error": "Unknown error occurred"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
