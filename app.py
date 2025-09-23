from flask import Flask, request, jsonify, render_template
import os
import fitz
import tempfile
import shutil
import requests
import base64

app = Flask(__name__, template_folder="templates", static_folder="static")
API_KEY = "AIzaSyAcPLSUgM9ZarS3D0CW0DmCzPLySBenQeU"
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"

def synthesize_final_memo(chunk_summaries):
    full_text = "\n\n".join(chunk_summaries)
    prompt = f"""
You are a professional VC analyst. Based on the summaries below, generate a single, clean investment memo using the exact structure and formatting provided. Do not add extra sections or repeat content. Use Markdown headings and spacing between sections.

Inject actual values for North Star Metrics based on pitch deck data. Format the VC Scorecard table using Markdown with borders. Show Confidence Score as a percentage (0–100%) and apply the following decision guide:

- >= 70% → Strong Candidate (Go)
- 51–69% → Conditional (monitor, more diligence)
- < 50% → High Risk (No-Go)

Ensure all section headings are bold and consistently formatted using Markdown ##.

The memo MUST follow this exact structure:

## 1. Executive Summary:
- Provide a single, concise paragraph that summarizes the company's core business, key highlights, and investment potential.

## 2. Company Overview:
- **Startup Name:**
- **Industry & Sector:**
- **Domain:**
- **Problem:**
- **Solution:**

## 3. The Founding Team:
- **Background and Expertise:**
- **Team Cohesion:**
- **Previous Exits/Successes:**
- **Intellectual Property:**

## 4. Market Opportunity:
- **Total Addressable Market (TAM):**
- **Serviceable Addressable Market (SAM):**
- **Competitive Landscape:**
- **Market Growth Rate (CAGR):**

## 5. Product & Technology:
- **Product Stage:**
- **Technical Barrier to Entry:**

## 6. Traction & Commercials:
- **Customer Metrics:**
- **CAC:**
- **LTV:**
- **Revenue Model:**
- **Revenue Run Rate:**
- **Industry Recognition:**

## 7. Financials & Projections:
- **Historical Revenue:**
- **Revenue Projections:**
- **Burn Rate:**
- **Runway:**
- **Use of Funds:**

## 8. Investment Terms & Exit Strategy:
- **Round Details:**
- **Pre-money Valuation:**
- **Exit Scenarios:**
- **Expected Returns:**

## 9. Final Recommendation:
- **Verdict:**
- **Confidence Score:**
- **VC Scorecard Calculation:**

| Category   | Score (1–10) | Weightage (%) | Weighted Score | Notes |
|------------|--------------|----------------|----------------|-------|
| Team       |              | 30             |                |       |
| Product    |              | 15             |                |       |
| Market     |              | 20             |                |       |
| Traction   |              | 20             |                |       |
| Financials |              | 10             |                |       |
| M&A/Exit   |              | 5              |                |       |
| **Total Score:** |        |                |                |       |

- **Top 3 North Star Metrics:**
- **Rationale:**

{full_text}
"""
    payload = { "contents": [ { "parts": [ { "text": prompt } ] } ] }
    headers = { "Content-Type": "application/json" }
    try:
        response = requests.post(GEMINI_API_URL, json=payload, headers=headers, timeout=60)
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except requests.exceptions.Timeout:
        return "⚠️ Gemini API timed out while synthesizing final memo. Try reducing deck size."
    except Exception as e:
        return f"⚠️ Error synthesizing final memo: {e}"

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

    chunk_size = 5
    chunks = [image_paths[i:i+chunk_size] for i in range(0, len(image_paths), chunk_size)]
    chunk_summaries = []

    for idx, chunk in enumerate(chunks):
        parts = [{"text": f"You are an expert VC analyst. Analyze the startup pitch deck images below. Chunk {idx+1} of {len(chunks)}."}]
        for img_path in chunk:
            with open(img_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
                parts.append({ "inline_data": { "mime_type": "image/png", "data": encoded } })
        payload = { "contents": [ { "parts": parts } ] }
        headers = { "Content-Type": "application/json" }
        try:
            response = requests.post(GEMINI_API_URL, json=payload, headers=headers, timeout=60)
            result = response.json()
            chunk_text = result["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.Timeout:
            chunk_text = f"⚠️ Gemini API timed out for chunk {idx+1}. Try reducing deck size."
        except Exception as e:
            chunk_text = f"⚠️ Error parsing chunk {idx+1}: {e}"
        chunk_summaries.append(chunk_text.strip())

    final_memo = synthesize_final_memo(chunk_summaries)
    shutil.rmtree(temp_dir)
    return jsonify({ "memo": final_memo })

if __name__ == "__main__":
    app.run(debug=True)

