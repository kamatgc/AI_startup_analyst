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
    full_text = "\n\n".join(chunk_summaries)
    
    synthesis_prompt = f"""    
**Investment Memo Structure (MANDATORY):**

The memo MUST follow this exact structure, using Markdown headings for each section.

**1. Executive Summary:**
- Provide a single, concise paragraph that summarizes the company's core business, key highlights, and investment potential.

**2. Company Overview:**
- **Startup Name:**
- **Industry & Sector:**
- **Domain:**
- **Problem:** What is the core problem the company is trying to solve?
- **Solution:** How does the company's product or service solve this problem?

**3. The Founding Team:**
- **Background and Expertise:** Synthesize the founders' professional history, relevant domain expertise, and educational backgrounds.
- **Team Cohesion:** Look for any evidence of how long the team has worked together, or previous collaborations.
- **Previous Exits/Successes:** Note any successful exits, acquisitions, or notable achievements of the founders.
- **Intellectual Property:** List any patents or unique IP mentioned.

**4. Market Opportunity:**
- **Total Addressable Market (TAM):** Extract the TAM value and its source (if provided).
- **Serviceable Addressable Market (SAM):** Extract the SAM value if specified.
- **Competitive Landscape:** Identify key competitors and detail the company's unique selling proposition (USP).
- **Market Growth Rate (CAGR):** Find the CAGR for the market.

**5. Product & Technology:**
- **Product Stage:** Determine if the product is a prototype, MVP, or a fully launched product.
- **Technical Barrier to Entry:** Assess if the technology is difficult to replicate.

**6. Traction & Commercials:**
- **Customer Metrics:** List all key customers, pilot programs, and strategic partnerships mentioned.
- **Customer Acquisition Cost (CAC):** Extract CAC if mentioned.
- **Customer Lifetime Value (LTV):** Extract LTV if mentioned.
- **Revenue Model:** Clearly explain how the company generates revenue. Be specific if possible.
- **Revenue Run Rate:** State the current or projected revenue run rate.
- **Industry Recognition:** List any awards, incubations, or mentions from key industry players.

**7. Financials & Projections:**
- **Historical Revenue:** Extract historical revenue data if available.
- **Revenue Projections:** State the financial forecasts for the next 3-5 years.
- **Burn Rate:** Find the burn rate if mentioned.
- **Runway:** Note the current runway if mentioned.
- **Use of Funds:** Detail how the company plans to use the investment.

**8. Investment Terms & Exit Strategy:**
- **Round Details:** Note the funding round size and type.
- **Pre-money Valuation:** State the pre-money valuation.
- **Exit Scenarios:** Describe any proposed exit strategies.
- **Expected Returns:** Note any projected return multiples.

**9. Final Recommendation:**
- **Verdict:** Based on the final score, provide a concise final recommendation to an investor. Use the following decision guide:
  - **>= 70 → Strong Candidate (Go)**
  - **51–69 → Conditional (monitor, more diligence)**
  - **< 50 → High Risk (No-Go)**
- **Confidence Score:** State the final calculated score from 0 to 100%.
- **VC Scorecard Calculation:**
  - Provide a table in Markdown with the following columns, ensuring the table has borders and proper alignment: **Category** (left aligned), **Score (1-10)** (center aligned), **Weightage (%)** (center aligned), **Weighted Score** (center aligned), and **Notes** (left aligned).
  - Score each category 1–10 (1 = poor, 10 = excellent) based on the information in the pitch deck.
  - Use the following fixed categories and weightages for the calculation:
    - **Team** (30%)
    - **Product** (15%)
    - **Market** (20%)
    - **Traction** (20%)
    - **Financials** (10%)
    - **M&A/Exit** (5%)
  - Show the weighted score for each category and sum them up to get the final score.
  - In the **Notes** column, provide a very brief one-line justification for the assigned score.
 
- **Top 3 North Star Metrics:**
  - Based on the company's industry, identify the top 3 North Star Metrics (NSMs) that matter most.
  - Evaluate the company's performance against these NSMs, citing any relevant data or metrics found in the deck and providing their actual values.
- **Rationale:** Briefly explain the primary reasons for your recommendation, highlighting key strengths and major concerns based on the NSM analysis and score breakdown.
 
The summaries to be synthesized are below:
 
{full_text}

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
