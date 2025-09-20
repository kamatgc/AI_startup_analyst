import base64
import os
import io
import json

from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from pdf2image import convert_from_bytes

app = Flask(__name__)
CORS(app)

# Configure the API key
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

@app.route("/", methods=["GET"])
def welcome():
    """A welcome message to test the API."""
    return "<h1>Hello, this is the AI Startup Analyst API.</h1><p>Please use the /ask endpoint with a POST request to submit a PDF.</p>"

@app.route("/ask", methods=["POST"])
def process_pdf():
    """Processes a PDF file and generates a startup evaluation report."""
    try:
        data = request.get_json(force=True)
        pdf_base64 = data.get('pdf_file')
        if not pdf_base64:
            return jsonify({"error": "No PDF file provided."}), 400

        # Decode the base64 string to bytes
        pdf_bytes = base64.b64decode(pdf_base64)
        
        # Convert PDF bytes to images
        images = convert_from_bytes(pdf_bytes)
        
        # Prepare content for Gemini API
        prompt_parts = [
            "You are a highly experienced Venture Capitalist. I will provide you with images of a startup's pitch deck, and you will generate a detailed investment memo. This memo should be thorough, professional, and structured for an investment committee. It should include the following sections:\n\n1.  **Executive Summary:** A concise overview of the investment opportunity, key terms, and the recommendation (Invest/Pass).\n2.  **The Team:** An analysis of the founders' background, expertise, and potential. Mention any red flags or areas of concern.\n3.  **The Product:** A detailed description of the product or service, its technology, and its competitive advantages.\n4.  **The Market:** An assessment of the total addressable market (TAM), market trends, and key competitors.\n5.  **Traction & Financials:** An analysis of key metrics such as user growth, revenue, burn rate, and financial projections. Note any assumptions made.\n6.  **Investment Thesis:** A clear, concise statement summarizing why this is a good investment opportunity.\n7.  **Key Risks:** A list of the top 3-5 risks associated with the investment, such as market risk, execution risk, and competitive risk. For each risk, provide a mitigation strategy.\n8.  **Recommendation:** A final, clear recommendation to the investment committee. Your analysis should be grounded in the data and images provided. If the information is not present in the pitch deck, make reasonable assumptions and state them explicitly. Your final output must be a single, comprehensive text document.",
        ]
        
        for image in images:
            # Convert PIL Image to bytes in-memory
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr = img_byte_arr.getvalue()
            
            prompt_parts.append({
                "mime_type": "image/jpeg",
                "data": img_byte_arr
            })
            
        # Call the Gemini Pro Vision model
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt_parts)

        # Return the generated text in a structured response
        return jsonify({"investment_memo": response.text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
