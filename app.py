from flask import Flask, request, jsonify, render_template
import os
import fitz  # PyMuPDF
import tempfile
import shutil
import time
from markdown import markdown
from google.generativeai import configure, GenerativeModel

app = Flask(__name__)
configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = GenerativeModel("gemini-pro")

def enrich_memo(memo_text):
    insights = []
    if "CAC" in memo_text and "LTV" in memo_text:
        insights.append("✅ CAC to LTV ratio appears healthy.")
    if "TAM" in memo_text and "early" in memo_text:
        insights.append("⚠️ TAM is early-stage. Consider market maturity.")
    if "exit" not in memo_text.lower():
        insights.append("⚠️ No clear exit strategy mentioned.")
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
        prompt = f"""You are an expert VC analyst. Analyze the startup pitch deck images below and generate a structured investment memo. Include:

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
        images = [{"mime_type": "image/png", "data": open(img, "rb").read()} for img in chunk]
        response = model.generate_content([prompt] + images)
        final_memo += response.text + "\n\n"

    final_memo = enrich_memo(final_memo)
    shutil.rmtree(temp_dir)

    return jsonify({"memo": final_memo})

if __name__ == "__main__":
    app.run(debug=True)

