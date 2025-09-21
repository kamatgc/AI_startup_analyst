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
    Analyzes the pitch deck text content using the Gemini API and the full, detailed prompt.
    """
    # The exact prompt you provided, with the text placeholder.
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
    
    {text_content}
    """

    prompt_parts = [
        {"text": synthesis_prompt}
    ]

    # Implement a retry mechanism with exponential backoff for a more robust application.
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

    print(f"Received file: {file.filename}")
    
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
            print("Failed to extract text from PDF. The file may be empty or unreadable.")
            return jsonify({"error": "Failed to extract text from PDF. The file may be empty or unreadable."}), 500

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500

    return jsonify({"error": "Unknown error occurred"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
