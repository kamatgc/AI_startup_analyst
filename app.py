import os
import json
import base64
import requests
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
from flask_cors import CORS
import traceback
import time

# Initialize Flask app
# The static_folder is set to '.' so Flask can serve files from the current directory.
app = Flask(__name__, static_folder='.')
CORS(app)

# --- Configuration and Constants ---
API_KEY = "AIzaSyCP1gTahHD0dTMhdQQEO2KlLr7HSti1R5I"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={API_KEY}"
CHUNK_SIZE = 5
UPLOAD_FOLDER = 'temp_uploads'
MAX_RETRIES = 5  # Maximum number of retries for API calls

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(os.path.join(os.getcwd(), UPLOAD_FOLDER))
    print(f"SERVER: Created upload folder at {UPLOAD_FOLDER}")

# --- Helper Functions ---
def pdf_to_base64_images(pdf_file_path):
    """
    Converts each page of a PDF file to a Base64-encoded JPEG image.
    This is a generator function to stream progress.
    """
    try:
        doc = fitz.open(pdf_file_path)
        images = []
        for i, page in enumerate(doc):
            # Render page to an image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            
            # Convert the pixmap to bytes in memory
            img_bytes = pix.tobytes("jpeg")
            
            # Encode to Base64
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            images.append(base64_image)
            
        doc.close()
        return images
    except Exception as e:
        print(f"SERVER: Error converting PDF to images: {e}")
        return []

def call_gemini_api_with_retries(payload):
    """
    Calls the Gemini API with a retry mechanism and exponential backoff.
    """
    for i in range(MAX_RETRIES):
        try:
            response = requests.post(
                GEMINI_API_URL, 
                headers={"Content-Type": "application/json"}, 
                data=json.dumps(payload),
                timeout=60 # Set a timeout to prevent hanging
            )
            response.raise_for_status() # Raise an exception for bad status codes
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"SERVER: Attempt {i+1}/{MAX_RETRIES} failed. Error: {e}")
            if i < MAX_RETRIES - 1:
                delay = 2 ** i # Exponential backoff
                print(f"SERVER: Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("SERVER: Max retries exceeded.")
                raise # Re-raise the exception after all retries fail

def generate_memo_chunk(chunk_images, chunk_number):
    """
    Generates a markdown summary for a chunk of images using the Gemini API.
    """
    print(f"SERVER: Generating memo for chunk {chunk_number}...")
    
    # Prompting the model to act as a pitch deck analyst
    prompt = f"""You are an experienced venture capital analyst. Your task is to analyze a startup pitch deck and create a concise investment memo. 

Analyze this document, focusing on the following aspects:
- Problem: Clearly state the problem the startup is solving.
- Solution: Describe the proposed solution or product.
- Target Market: Identify the target audience and market size.
- Team: Assess the team's background, expertise, and experience.
- Traction & Metrics: Summarize key performance indicators, milestones, and achievements.
- Competition: Identify key competitors and the startup's competitive advantage.
- Business Model: Explain how the company plans to generate revenue.
- Ask: What is the funding amount being requested and for what purpose.

Combine your analysis into a single, cohesive paragraph of a professional investment memo.

The following images are a part of a startup pitch deck. Analyze them and provide a detailed markdown-formatted summary of your findings.
"""
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    
    for image_data in chunk_images:
        payload["contents"][0]["parts"].append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": image_data
            }
        })
    
    try:
        api_response = call_gemini_api_with_retries(payload)
        summary = api_response['candidates'][0]['content']['parts'][0]['text']
        return summary
    except Exception as e:
        print(f"SERVER: Failed to generate memo for chunk {chunk_number}. Error: {e}")
        return f"**Analysis for Chunk {chunk_number} Failed:** An error occurred during processing. Please try again or with a different file."

def synthesize_final_memo(chunk_summaries):
    """
    Synthesizes the individual chunk summaries into a single, cohesive final investment memo.
    """
    print("SERVER: Synthesizing final memo...")
    
    prompt = f"""You are an expert venture capital analyst. You have been provided with several paragraphs, each summarizing a different section of a single startup pitch deck. Your task is to combine these summaries into a single, comprehensive, and cohesive final investment memo.

The memo should have a professional and objective tone. It must include the following sections, formatted with bold headings:

- **Executive Summary:** A concise, high-level overview of the investment opportunity.
- **Problem & Solution:** A summary of the core problem the startup is solving and their proposed solution.
- **Market Opportunity:** An overview of the target market, size, and go-to-market strategy.
- **Traction & Financials:** Key metrics, milestones, and a summary of the business model.
- **Team:** An assessment of the founding team's experience and qualifications.
- **Competitive Landscape:** A brief analysis of competitors and the startup's competitive advantage.
- **Request for Funding:** The amount requested and the intended use of funds.
- **Final Recommendation:** A clear, final go/no-go recommendation based on the data provided, including a **VC Scorecard** (scores from 1-10 for Problem, Solution, Team, Market, and Traction) and a **Confidence Score** (from 1-10) to reflect the clarity and completeness of the provided data.

Here are the individual summary paragraphs:
{"\n".join(chunk_summaries)}
"""
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    
    try:
        api_response = call_gemini_api_with_retries(payload)
        final_memo = api_response['candidates'][0]['content']['parts'][0]['text']
        return final_memo
    except Exception as e:
        print(f"SERVER: Failed to synthesize final memo. Error: {e}")
        return "**Final Memo Synthesis Failed:** An error occurred while generating the final report. Please try again or check the provided file."

# --- API Routes ---
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/analyze', methods=['POST'])
@stream_with_context
def analyze():
    print("SERVER: Received POST request for /analyze.")
    temp_path = None
    try:
        # Check for file in request
        if 'file' not in request.files:
            print("SERVER ERROR: No file part in request.")
            yield json.dumps({"error": "No file part"}) + '\n'
            return

        file = request.files['file']
        if file.filename == '':
            print("SERVER ERROR: No selected file.")
            yield json.dumps({"error": "No selected file"}) + '\n'
            return

        # Save the file temporarily
        temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(temp_path)
        print(f"SERVER: Saved file to {temp_path}")
        yield json.dumps({"status": "File uploaded successfully. Processing..."}) + '\n'

        # Convert PDF to images
        yield json.dumps({"status": "Converting PDF to images..."}) + '\n'
        all_images = pdf_to_base64_images(temp_path)
        if not all_images:
            yield json.dumps({"error": "Failed to convert PDF to images. Please ensure it's a valid PDF."}) + '\n'
            return

        # Process chunks
        chunk_summaries = []
        num_chunks = (len(all_images) + CHUNK_SIZE - 1) // CHUNK_SIZE
        for i in range(num_chunks):
            start_index = i * CHUNK_SIZE
            end_index = min(start_index + CHUNK_SIZE, len(all_images))
            chunk_images = all_images[start_index:end_index]
            
            print(f"SERVER: Analyzing chunk {i + 1} of {num_chunks} (pages {start_index + 1} to {end_index})...")
            yield json.dumps({"status": f"Analyzing chunk {i + 1} of {num_chunks}..."}) + '\n'
            chunk_summary = generate_memo_chunk(chunk_images, i + 1)
            chunk_summaries.append(chunk_summary)
            print(f"SERVER: Chunk {i + 1} analysis complete.")

        print("SERVER: All chunks analyzed. Now synthesizing final memo...")
        yield json.dumps({"status": "Synthesizing final investment memo..."}) + '\n'
        final_memo = synthesize_final_memo(chunk_summaries)
        
        print("SERVER: Final memo synthesis complete. Sending response.")
        yield json.dumps({"status": "Analysis complete.", "memo": final_memo}) + '\n'
        
    except Exception as e:
        print(f"SERVER FATAL ERROR: {e}")
        traceback.print_exc()
        yield json.dumps({"error": "An unexpected server error occurred."}) + '\n'
    finally:
        if temp_path and os.path.exists(temp_path):
            print(f"SERVER: Cleaning up temporary file: {temp_path}")
            os.remove(temp_path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5000))
