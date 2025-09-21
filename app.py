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
# NOTE: Using a placeholder for the API key. In a real-world app, you should
# use environment variables for sensitive information.
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
        print(f"SERVER: PDF has {doc.page_count} pages.")
        
        all_images = []
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            image_buffer = pix.tobytes(output="jpeg", jpg_quality=95)
            all_images.append(base64.b64encode(image_buffer).decode('utf-8'))
        
        doc.close()
        return all_images
    except Exception as e:
        print(f"Error converting PDF to images: {e}")
        return None

def generate_memo_chunk(image_chunk, chunk_num):
    """
    Sends a chunk of images to the Gemini API and returns the generated text.
    Includes retry logic with exponential backoff.
    """
    prompt = f"Analyze these images from a startup pitch deck (Chunk {chunk_num}). Identify key points about the company, its product, market, team, and financial projections. Structure your response as a cohesive section of an investment memo. Include an executive summary for this chunk."

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ] + [
                    {"inlineData": {"mimeType": "image/jpeg", "data": img}} for img in image_chunk
                ]
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    retries = 3
    delay = 1
    
    for attempt in range(retries):
        try:
            print(f"SERVER: Generating memo for chunk {chunk_num}...")
            print(f"SERVER: Attempting API call (Retry {attempt + 1}/{retries})...")
            response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(payload), timeout=120)
            response.raise_for_status()
            
            result = response.json()
            candidate = result.get('candidates')[0] if result.get('candidates') else None
            if not candidate or not candidate.get('content') or not candidate['content'].get('parts'):
                raise ValueError("Invalid API response format")
                
            text = candidate['content']['parts'][0]['text']
            return text
            
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error for chunk {chunk_num}: {http_err}")
            if response.status_code in [429, 500, 503] and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except requests.exceptions.RequestException as req_err:
            print(f"Request error for chunk {chunk_num}: {req_err}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except (ValueError, IndexError) as parse_err:
            print(f"JSON parsing error for chunk {chunk_num}: {parse_err}")
            raise
    
    raise Exception("Failed to get a response from the API after multiple retries.")

def synthesize_final_memo(chunk_summaries):
    """
    Synthesizes the final investment memo from the chunk summaries based on a structured prompt.
    """
    full_text = "\n\n---\n\n".join(chunk_summaries)
    
    synthesis_prompt = f"""
You are an expert financial analyst. You have been provided with several summaries of a startup pitch deck.
    
Your task is to synthesize all of the provided summaries into a single, professional investment memo.
    
Use the following structure and fill in the details from the summaries. If a specific data point is not available, state "Information not available in the provided materials."
    
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
                "parts": [{"text": synthesis_prompt}]
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    retries = 3
    delay = 1

    for attempt in range(retries):
        try:
            response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(payload), timeout=180)
            response.raise_for_status()
            
            result = response.json()
            candidate = result.get('candidates')[0] if result.get('candidates') else None
            if not candidate or not candidate.get('content') or not candidate['content'].get('parts'):
                raise ValueError("Invalid API response format")
            
            return candidate['content']['parts'][0]['text']
        
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error during synthesis: {http_err}")
            if response.status_code in [429, 500, 503] and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except requests.exceptions.RequestException as req_err:
            print(f"Request error during synthesis: {req_err}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except (ValueError, IndexError) as parse_err:
            print(f"JSON parsing error during synthesis: {parse_err}")
            raise

    raise Exception("Failed to synthesize memo after multiple retries.")


# --- Routes ---
@app.route('/')
def serve_index():
    print("SERVER: Request received for root URL '/'. Serving index.html...")
    return send_from_directory('.', 'index.html')

@app.route('/ask', methods=['POST'])
def handle_ask():
    print("SERVER: Received POST request at /ask. Checking for file...")
    # This is a streaming response to update the frontend in real-time.
    # The `stream_with_context` is crucial here for long-running processes.
    
    def generate():
        temp_path = None
        try:
            if 'pdf_file' not in request.files:
                print("SERVER: Error: No file part in the request.")
                yield json.dumps({"error": "No file part in the request."}) + '\n'
                return

            file = request.files['pdf_file']
            
            if file.filename == '':
                print("SERVER: Error: No selected file.")
                yield json.dumps({"error": "No selected file."}) + '\n'
                return
            
            print(f"SERVER: File '{file.filename}' received. Saving to temporary path...")
            temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(temp_path)
            print(f"SERVER: File saved to '{temp_path}'. Initiating analysis...")

            yield json.dumps({"status": "Processing PDF pages..."}) + '\n'
            all_images = pdf_to_base64_images(temp_path)
            if not all_images:
                print("SERVER: Failed to process PDF file.")
                yield json.dumps({"error": "Failed to process PDF file."}) + '\n'
                return

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
    
    return Response(stream_with_context(generate()), mimetype='application/json')

if __name__ == '__main__':
    # When running locally, you might use app.run().
    # On Render, Gunicorn will handle the server, using the Procfile settings.
    print("SERVER: Application started. Waiting for requests.")
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
