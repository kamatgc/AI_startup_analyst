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

Inject actual values for North Star Metrics based on pitch deck data. Format the VC Scorecard table using HTML with visible borders. Show Confidence Score as a percentage (0–100%) and apply the following decision guide:

- >= 70% → Strong Candidate (Go)
- 51–69% → Conditional (monitor, more diligence)
- < 50% → High Risk (No-Go)

Ensure all section headings are bold and consistently formatted using Markdown ##.

The memo MUST follow this exact structure:

## 1. Executive Summary:
## 2. Company Overview:
## 3. The Founding Team:
## 4. Market Opportunity:
## 5. Product & Technology:
## 6. Traction & Commercials:
## 7. Financials & Projections:
## 8. Investment Terms & Exit Strategy:
## 9. Final Recommendation:
- **Verdict:**
- **Confidence Score:**
- **VC Scorecard Calculation:**

<table class="table-auto border border-gray-400 border-collapse">
<thead>
<tr>
<th class="border px-2 py-1">Category</th>
<th class="border px-2 py-1">Score (1–10)</th>
<th class="border px-2 py-1">Weightage (%)</th>
<th class="border px-2 py-1">Weighted Score</th>
<th class="border px-2 py-1">Notes</th>
</tr>
</thead>
<tbody>
<tr><td class="border px-2 py-1">Team</td><td class="border px-2 py-1"></td><td class="border px-2 py-1">30</td><td class="border px-2 py-1"></td><td class="border px-2 py-1"></td></tr>
<tr><td class="border px-2 py-1">Product</td><td class="border px-2 py-1"></td><td class="border px-2 py-1">15</td><td class="border px-2 py-1"></td><td class="border px-2 py-1"></td></tr>
<tr><td class="border px-2 py-1">Market</td><td class="border px-2 py-1"></td><td class="border px-2 py-1">20</td><td class="border px-2 py-1"></td><td class="border px-2 py-1"></td></tr>
<tr><td class="border px-2 py-1">Traction</td><td class="border px-2 py-1"></td><td class="border px-2 py-1">20</td><td class="border px-2 py-1"></td><td class="border px-2 py-1"></td></tr>
<tr><td class="border px-2 py-1">Financials</td><td class="border px-2 py-1"></td><td class="border px-2 py-1">10</td><td class="border px-2 py-1"></td><td class="border px-2 py-1"></td></tr>
<tr><td class="border px-2 py-1">M&A/Exit</td><td class="border px-2 py-1"></td><td class="border px-2 py-1">5</td><td class="border px-2 py-1"></td><td class="border px-2 py-1"></td></tr>
<tr><td class="border px-2 py-1 font-bold" colspan="3">Total Score:</td><td class="border px-2 py-1"></td><td class="border px-2 py-1"></td></tr>
</tbody>
</table>

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

