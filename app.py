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

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(os.path.join(os.getcwd(), UPLOAD_FOLDER))

# --- Helper Functions ---
def pdf_to_base64_images(pdf_file_path):
    """
    Converts each page of a PDF file to a Base64-encoded JPEG image.
    This is a generator function to stream progress.
    """
    try:
        doc = fitz.open(pdf_file_path)
        num_pages = doc.page_count
        images = []
        
        print("Server: Starting PDF conversion...")
        yield json.dumps({"status": f"Converting PDF to images (0/{num_pages} pages completed)..."}) + '\n'
        
        for page_num in range(num_pages):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            image_buffer = pix.tobytes(output='jpeg')
            images.append(base64.b64encode(image_buffer).decode('utf-8'))
            
            print(f"Server: Converted page {page_num + 1} of {num_pages}.")
            yield json.dumps({"status": f"Converting PDF to images ({page_num + 1}/{num_pages} pages completed)..."}) + '\n'
            
        doc.close()
        print("Server: PDF conversion complete.")
        yield json.dumps({"status": "PDF conversion complete."}) + '\n'
        
        return images
    except Exception as e:
        print(f"Error converting PDF to images: {e}")
        traceback.print_exc()
        yield json.dumps({"error": "Failed to process PDF file during conversion."}) + '\n'
        return []

def call_gemini_api(prompt_text, images=None):
    """
    Calls the Gemini API with a text prompt and optional images.
    Implements a simple retry mechanism for robustness.
    """
    retries = 3
    for i in range(retries):
        try:
            parts = [{"text": prompt_text}]
            if images:
                for img_base64 in images:
                    parts.append({"inlineData": {"mimeType": "image/jpeg", "data": img_base64}})
            
            payload = {
                "contents": [{"parts": parts}]
            }
            
            response = requests.post(GEMINI_API_URL, json=payload, timeout=60)
            response.raise_for_status()
            
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e} - Retrying...")
            time.sleep(2 ** i)
        except Exception as e:
            print(f"An error occurred during API call: {e} - Retrying...")
            traceback.print_exc()
            time.sleep(2 ** i)
    raise Exception(f"Failed to get a successful response after {retries} retries.")

def generate_memo_chunk(images, chunk_number):
    """
    Generates a summary for a chunk of images.
    """
    chunk_prompt = f"""
    You are an expert financial analyst. You have been provided with a chunk of a startup pitch deck (images {chunk_number}).
    
    Your task is to summarize the key information from these pages, including:
    - Team details (names, roles, background)
    - Product features and stage
    - Market size and growth
    - Financials (revenue, burn rate, runway, projections)
    - Traction (customers, partnerships, awards)
    - Investment terms (valuation, funding round)
    
    Format the summary as concise, easy-to-read text.
    """
    return call_gemini_api(chunk_prompt, images=images)

def synthesize_final_memo(summaries):
    """
    Synthesizes all chunk summaries into a single, professional investment memo.
    """
    full_text = "\\n\\n".join(summaries)
    
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
    
    return call_gemini_api(synthesis_prompt)

# --- Routes ---
@app.route('/')
def serve_index():
    """Serve the index.html file from the same directory."""
    print("Server: Serving index.html")
    return send_from_directory('.', 'index.html')

@app.route('/ask', methods=['POST'])
def ask_ai():
    print("Server: Received POST request at /ask")
    if 'pdf_file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(temp_path)
        
        @stream_with_context
        def generate():
            try:
                print("Server: File received. Initiating PDF processing...")
                image_updates_generator = pdf_to_base64_images(temp_path)
                
                all_images = []
                for update in image_updates_generator:
                    yield update
                
                # The generator returns the full list of images after yielding all updates
                try:
                    all_images = next(image_updates_generator)
                except StopIteration:
                    pass

                if not all_images:
                    yield json.dumps({"error": "Failed to process PDF file."}) + '\n'
                    return

                chunk_summaries = []
                num_chunks = (len(all_images) + CHUNK_SIZE - 1) // CHUNK_SIZE
                
                for i in range(num_chunks):
                    start_index = i * CHUNK_SIZE
                    end_index = min(start_index + CHUNK_SIZE, len(all_images))
                    chunk_images = all_images[start_index:end_index]
                    
                    yield json.dumps({"status": f"Analyzing chunk {i + 1} of {num_chunks}..."}) + '\n'
                    print(f"Server: Analyzing chunk {i + 1} of {num_chunks}...")
                    chunk_summary = generate_memo_chunk(chunk_images, i + 1)
                    chunk_summaries.append(chunk_summary)

                yield json.dumps({"status": "Synthesizing final investment memo..."}) + '\n'
                print("Server: Synthesizing final investment memo...")
                final_memo = synthesize_final_memo(chunk_summaries)
                
                yield json.dumps({"status": "Analysis complete.", "memo": final_memo}) + '\n'
                
            except Exception as e:
                print(f"FATAL ERROR: {e}")
                traceback.print_exc()
                yield json.dumps({"error": "An unexpected server error occurred."}) + '\n'
            finally:
                if temp_path and os.path.exists(temp_path):
                    print(f"Server: Cleaning up temporary file: {temp_path}")
                    os.remove(temp_path)
    
    return Response(stream_with_context(generate()), mimetype='application/json')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
