from flask import Flask, request, jsonify, render_template
import os
import fitz  # PyMuPDF
import tempfile
import shutil
import requests
import base64

app = Flask(__name__)
API_KEY = "AIzaSyAcPLSUgM9ZarS3D0CW0DmCzPLySBenQeU"
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"

def enrich_memo(memo_text):
    insights = []
    lower_text = memo_text.lower()

    if "cac" in lower_text and "ltv" in lower_text:
        insights.append("✅ CAC to LTV ratio appears healthy.")
    if "tam" in lower_text and "early" in lower_text:
        insights.append("⚠️ TAM is early-stage. Consider market maturity.")
    exit_keywords = ["exit", "ipo", "m&a", "acquisition", "return projections"]
    if not any(keyword in lower_text for keyword in exit_keywords):
        insights.append("⚠️ No clear exit strategy mentioned.")

    print("🔍 Final memo text:\n", memo_text)
    return memo_text + "\n\n🔍 Insights:\n" + "\n".join(insights)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    uploaded_file = request.files["file"]
    temp_dir = tempfile.mkdtemp()
    pdf_path = os.path.join(temp_dir, uploaded_file.filename)
    uploaded_file.save(pdf_path)

    doc = fitz.open(pdf_path)
    image_paths = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=300)
        image_path = os.path.join(temp_dir, f"page_{i+1}.png")
        pix.save(image_path)
        image_paths.append(image_path)

    chunks = []
    chunk_size = 5
    for i in range(0, len(image_paths), chunk_size):
        chunk = image_paths[i:i+chunk_size]
        chunks.append(chunk)

    final_memo = ""
    for idx, chunk in enumerate(chunks):
        parts = [
            {
                "text": f"""You are an expert VC analyst. Analyze the startup pitch deck images below and generate a structured investment memo. Include:

- Executive Summary
- Overview (Startup Name, Domain, Demographic)
- Problem
- Solution
- Traction
- Business Model
- Financials
- Team
- Market Opportunity
- Risks
- Ask
- VC Scorecard (Team, Product, Market, Traction, TAM/Exit, M&A/Exit)
- Final Verdict (Go/No-Go)
- Confidence Score
- Top 3 North Star Metrics

Chunk {idx+1} of {len(chunks)}. Provide markdown output."""
            }
        ]

        for img_path in chunk:
            with open(img_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
                parts.append({
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": encoded
                    }
                })

        payload = { "contents": [ { "parts": parts } ] }
        headers = { "Content-Type": "application/json" }
        response = requests.post(GEMINI_API_URL, json=payload, headers=headers)
        result = response.json()
        print(f"🔍 Gemini raw response (chunk {idx+1}):\n", result)

        try:
            chunk_text = result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            chunk_text = f"⚠️ Error parsing Gemini response: {e}"

        final_memo += chunk_text + "\n\n"

    final_memo = enrich_memo(final_memo)
    shutil.rmtree(temp_dir)

    return jsonify({ "memo": final_memo })

if __name__ == "__main__":
    app.run(debug=True)

