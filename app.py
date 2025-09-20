import os
import json
import base64
import requests
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import traceback

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# --- Configuration and Constants ---
# Use environment variable for the API key (IMPORTANT for security)
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("FATAL ERROR: The GEMINI_API_KEY environment variable is not set.")
    # In a real app, you might want to handle this more gracefully.
    # For now, we will just continue, but the API calls will fail.
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={API_KEY}"
CHUNK_SIZE = 5
UPLOAD_FOLDER = 'temp_uploads'

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(os.path.join(os.getcwd(), UPLOAD_FOLDER))

# --- Helper Functions ---
def pdf_to_base64_images(pdf_file_path):
    """
    Converts each page of a PDF file to a Base64-encoded JPEG image.
    """
    images = []
    try:
        doc = fitz.open(pdf_file_path)
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            image_buffer = pix.tobytes("jpeg")
            images.append(base64.b64encode(image_buffer).decode('utf-8'))
        doc.close()
    except Exception as e:
        print(f"ERROR: Failed to process PDF with PyMuPDF: {e}")
        traceback.print_exc()
        return []
    return images

def generate_memo_chunk(base64_images, chunk_number):
    """
    Sends a chunk of images to the Gemini API to generate a mini-memo for that section.
    """
    prompt = f"""
    You are an expert financial analyst. You are reviewing a pitch deck. This is part {chunk_number} of a multi-part review.
    
    Review the following images and provide a concise summary of the key information presented. Your summary should focus on the following:
    - **Traction & Metrics**: Customers, pilots, key partnerships, revenue, and growth signals.
    - **Financials**: Any mention of revenue, burn rate, runway, or financial projections.
    - **Team**: Key team members, their experience, or any intellectual property.
    - **Market**: Market size, competition, or unique selling proposition.
    - **Industry/Domain**: Clearly identify the company's industry, sector, and domain.
    
    Format your response as a single markdown paragraph or a list of bullet points. Do not include a final recommendation or a full memo structure. This is just a summary of this section. If no information is found, state "No relevant information found in this section."
    """

    contents = [{
        "parts": [{"text": prompt}]
    }]

    for img in base64_images:
        contents[0]["parts"].append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": img
            }
        })
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.2,
            "topK": 10,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    }
    
    try:
        response = requests.post(API_URL, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        return result.get('candidates')[0].get('content').get('parts')[0].get('text')
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed for chunk {chunk_number}: {e}")
        traceback.print_exc()
        return f"An error occurred during the API call for chunk {chunk_number}: {e}"
        
def synthesize_final_memo(chunk_summaries):
    """
    Synthesizes all chunk summaries into a single, cohesive investment memo.
    """
    full_text = "\n\n".join(chunk_summaries)
    
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
        "contents": [{"parts": [{"text": synthesis_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.2,
            "topK": 10,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    }
    
    try:
        response = requests.post(API_URL, json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        return result.get('candidates')[0].get('content').get('parts')[0].get('text')
    except requests.exceptions.RequestException as e:
        print(f"ERROR: API request failed during synthesis: {e}")
        traceback.print_exc()
        return f"An error occurred during the final synthesis: {e}"

# --- API Endpoint ---
@app.route('/analyze_pitch_deck', methods=['POST'])
def analyze_pitch_deck():
    """
    API endpoint to receive a PDF file, analyze it in chunks, and return an investment memo.
    """
    
    def generate():
        yield json.dumps({"status": "Received pitch deck. Starting analysis."}) + '\n'

        if 'pdf' not in request.files:
            yield json.dumps({"error": "No file part in the request"}).encode('utf-8')
            return

        file = request.files['pdf']
        if file.filename == '':
            yield json.dumps({"error": "No selected file"}).encode('utf-8')
            return

        if file:
            temp_path = ""
            try:
                # Save the file temporarily
                temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(temp_path)
                
                yield json.dumps({"status": "Processing PDF file..."}) + '\n'
                
                # Get the number of pages for ETA calculation
                doc_pages = fitz.open(temp_path).page_count
                # Simple ETA calculation: 10s per chunk + 30s for synthesis
                estimated_seconds = (doc_pages / CHUNK_SIZE) * 10 + 30 
                yield json.dumps({"status": f"Found {doc_pages} pages.", "eta_seconds": estimated_seconds}) + '\n'

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
                    
                    yield json.dumps({"status": f"Analyzing chunk {i + 1} of {num_chunks}..."}) + '\n'
                    chunk_summary = generate_memo_chunk(chunk_images, i + 1)
                    chunk_summaries.append(chunk_summary)

                yield json.dumps({"status": "Synthesizing final investment memo..."}) + '\n'
                final_memo = synthesize_final_memo(chunk_summaries)
                
                yield json.dumps({"status": "Analysis complete.", "memo": final_memo}) + '\n'
                
            except Exception as e:
                print(f"FATAL ERROR: {e}")
                traceback.print_exc()
                yield json.dumps({"error": "An unexpected server error occurred."}) + '\n'
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
    
    return Response(stream_with_context(generate()), mimetype='application/json')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
