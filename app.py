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
# NOTE: The API_KEY below is for demonstration purposes only. You should manage it securely.
API_KEY = "AIzaSyCP1gTahHD0dTMhdQQEO2KlLr7HSti1R5I"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={API_KEY}"
CHUNK_SIZE = 5
UPLOAD_FOLDER = 'temp_uploads'

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
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            image_buffer = pix.tobytes("jpeg")
            encoded_image = base64.b64encode(image_buffer).decode('utf-8')
            images.append({"mimeType": "image/jpeg", "data": encoded_image})
        return images
    except Exception as e:
        print(f"Error converting PDF to images: {e}")
        return None

def generate_memo_chunk(images, chunk_num):
    """
    Generates a markdown summary for a chunk of images using the Gemini API.
    """
    try:
        # Construct the prompt with system instructions
        system_prompt = (
            "You are an expert financial analyst. Your task is to analyze a pitch deck. "
            "For this section of the deck, provide a detailed markdown summary "
            "focusing on key information like company name, product description, market size, "
            "business model, traction, team, and financial projections if present. "
            "Be concise but informative. Do not add titles or headings. Do not repeat "
            "information from previous chunks."
        )
        
        # Prepare the parts for the request
        parts = [
            {"text": system_prompt},
            {"text": f"Analyze the following images from chunk {chunk_num} of a pitch deck. "
                     "Extract all relevant information to build a comprehensive investment memo. "
                     "Your response should be a concise markdown summary of this chunk."}
        ]
        
        # Add images to the parts
        parts.extend([{"inlineData": img} for img in images])

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "topK": 40
            },
            "systemInstruction": {
                "parts": [{"text": "You are a professional investment analyst. Do not generate titles or headings."}]
            }
        }
        
        response = requests.post(GEMINI_API_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
        response.raise_for_status()
        
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']

    except Exception as e:
        print(f"Error generating memo chunk: {e}")
        return f"Error: Failed to analyze this chunk. Details: {str(e)}"

def synthesize_final_memo(chunk_summaries):
    """
    Synthesizes the individual chunk summaries into a single, cohesive investment memo.
    """
    try:
        # Construct the combined prompt for final synthesis
        combined_text = "\n\n".join(chunk_summaries)
        
        system_prompt = (
            "You are an expert financial analyst. You have been provided with several summaries of a startup pitch deck. "
            "Your task is to synthesize all of the provided summaries into a single, professional investment memo. "
            "Use the following structure and fill in the details from the summaries. If a specific data point is not available, state 'Information not available in the provided materials.'"
        )
        
        user_prompt = f"""
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
 
{combined_text}
"""

        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "topK": 40
            },
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            }
        }
        
        response = requests.post(GEMINI_API_URL, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
        response.raise_for_status()
        
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']

    except Exception as e:
        print(f"Error synthesizing final memo: {e}")
        return f"Error: Failed to synthesize the final memo. Details: {str(e)}"

@app.route('/')
def serve_index():
    print("SERVER: Request received for root URL '/'. Serving index.html...")
    return send_from_directory('.', 'index.html')

@app.route('/analyze', methods=['POST'])
def analyze_pitch_deck():
    """
    Analyzes an uploaded PDF pitch deck and streams the result in real-time.
    """
    print("SERVER: Received POST request for /analyze.")

    if 'pdf_file' not in request.files:
        print("SERVER: No file part in the request.")
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['pdf_file']

    if file.filename == '':
        print("SERVER: No selected file.")
        return jsonify({"error": "No selected file"}), 400

    def generate():
        temp_path = None
        try:
            # Save the file to a temporary location
            temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
            
            # --- The fix for the ValueError ---
            # Read the file content into memory before saving to avoid the "closed file" error
            file_content = file.read()
            with open(temp_path, 'wb') as temp_file:
                temp_file.write(file_content)
            # --- End of fix ---

            print(f"SERVER: Saved uploaded file to {temp_path}")

            yield json.dumps({"status": "Extracting images from PDF..."}) + '\n'
            all_images = pdf_to_base64_images(temp_path)
            
            if not all_images:
                yield json.dumps({"error": "Failed to process PDF file."}) + '\n'
                return

            chunk_summaries = []
            num_chunks = (len(all_images) + CHUNK_SIZE - 1) // CHUNK_SIZE
            
            for i in range(num_chunks):
                start_index = i * CHUNK_SIZE
                end_index = min(start_index + CHUNK_SIZE, len(all_images))
                chunk_images = all_images[start_index:end_index]
                
                print(f"SERVER: Analyzing chunk {i + 1} of {num_chunks} (pages {start_index + 1} to {end_index})...")
                yield json.dumps({"status": f"Analyzing chunk {i + 1} of {num_chunks}... ({len(chunk_images)} pages)"}) + '\n'
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
    
    return Response(stream_with_context(generate()), mimetype='application/json')

if __name__ == '__main__':
    # You can specify the host to be '0.0.0.0' to make it accessible externally
    app.run(debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5000))
