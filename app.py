from flask import Flask, request, Response, render_template, stream_with_context, jsonify
import os
import fitz
import tempfile
import shutil
import requests
import base64
from datetime import datetime
import json
import uuid

app = Flask(__name__, template_folder="templates", static_folder="static")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

API_KEY = "AIzaSyAcPLSUgM9ZarS3D0CW0DmCzPLySBenQeU"
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"

def timestamped(msg):
    return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    uploaded_file = request.files["file"]
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    uploaded_file.save(file_path)
    return jsonify({ "file_id": file_id })

@app.route("/stream/<file_id>")
def stream(file_id):
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    if not os.path.exists(file_path):
        return "File not found", 404

    def generate():
        start_time = datetime.now()
        temp_dir = tempfile.mkdtemp()
        doc = fitz.open(file_path)
        yield f"data: {timestamped(f'PDF uploaded. Total pages: {len(doc)}')}\n\n"

        estimated_sec = max(30, len(doc) * 8)
        estimated_min = estimated_sec // 60
        yield f"data: {timestamped(f'Estimated processing time: {estimated_min} min {estimated_sec % 60} sec')}\n\n"

        image_paths = []
        for i, page in enumerate(doc):
            yield f"data: {timestamped(f'Scanning page {i+1} of {len(doc)}...')}\n\n"
            pix = page.get_pixmap(dpi=300)
            image_path = os.path.join(temp_dir, f"page_{i+1}.png")
            pix.save(image_path)
            image_paths.append(image_path)

        chunk_size = 5
        chunks = [image_paths[i:i+chunk_size] for i in range(0, len(image_paths), chunk_size)]
        yield f"data: {timestamped(f'Chunking complete: {len(chunks)} chunks, {chunk_size} pages per chunk')}\n\n"

        chunk_summaries = []
        for idx, chunk in enumerate(chunks):
            yield f"data: {timestamped(f'Analyzing chunk {idx+1} of {len(chunks)}...')}\n\n"
            parts = [{"text": f"You are an expert VC analyst. Analyze the startup pitch deck images below. Chunk {idx+1} of {len(chunks)}."}]
            for img_path in chunk:
                with open(img_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                    parts.append({ "inline_data": { "mime_type": "image/png", "data": encoded } })
            payload = { "contents": [ { "parts": parts } ] }
            headers = { "Content-Type": "application/json" }
            try:
                response = requests.post(GEMINI_API_URL, json=payload, headers=headers, timeout=120)
                result = response.json()
                chunk_text = result["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                chunk_text = f"⚠️ Error parsing chunk {idx+1}: {e}"
            chunk_summaries.append(chunk_text.strip())

        yield f"data: {timestamped('Now synthesizing final memo...')}\n\n"
        full_text = "\n\n".join(chunk_summaries)

        # Revert to approved v22 memo format
        prompt = f"""
You are a professional VC analyst. Based on the summaries below, generate a clean investment memo using the following structure and formatting. Do not add extra sections or change the layout. Use Markdown headers and spacing exactly as shown.

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

<table>
<tr><th>Category</th><th>Score (1-10)</th><th>Weightage (%)</th><th>Weighted Score</th><th>Notes</th></tr>
<tr><td>Team</td><td></td><td>30</td><td></td><td></td></tr>
<tr><td>Product</td><td></td><td>15</td><td></td><td></td></tr>
<tr><td>Market</td><td></td><td>20</td><td></td><td></td></tr>
<tr><td>Traction</td><td></td><td>20</td><td></td><td></td></tr>
<tr><td>Financials</td><td></td><td>10</td><td></td><td></td></tr>
<tr><td>M&A/Exit</td><td></td><td>5</td><td></td><td></td></tr>
<tr><td colspan="3">Total Score:</td><td></td><td></td></tr>
</table>

- **Top 3 North Star Metrics:**
- **Rationale:**

{full_text}
"""
        payload = { "contents": [ { "parts": [ { "text": prompt } ] } ] }
        headers = { "Content-Type": "application/json" }
        try:
            response = requests.post(GEMINI_API_URL, json=payload, headers=headers, timeout=120)
            result = response.json()
            memo = result["candidates"][0]["content"]["parts"][0]["text"]
            yield f"data: {timestamped('Final memo synthesis complete. Sending response...')}\n\n"
            yield f"data: memo:{json.dumps(memo)}\n\n"
        except Exception as e:
            yield f"data: {timestamped(f'⚠️ Memo synthesis failed: {e}')}\n\n"
            yield f"data: memo:{json.dumps('⚠️ Memo synthesis failed.')}\n\n"

        shutil.rmtree(temp_dir)
        os.remove(file_path)

        # Actual duration
        end_time = datetime.now()
        duration = end_time - start_time
        total_sec = int(duration.total_seconds())
        total_min = total_sec // 60
        yield f"data: {timestamped(f'Actual processing time: {total_min} min {total_sec % 60} sec')}\n\n"

    return Response(stream_with_context(generate()), content_type='text/event-stream')

if __name__ == "__main__":
    app.run(debug=True)

