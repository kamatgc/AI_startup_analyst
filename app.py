from flask import Flask, request, jsonify, render_template
import os
import fitz
import tempfile
import shutil
import requests
import base64
from datetime import datetime

app = Flask(__name__, template_folder="templates", static_folder="static")
API_KEY = "AIzaSyAcPLSUgM9ZarS3D0CW0DmCzPLySBenQeU"
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"

def timestamped(msg):
    return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"

def synthesize_final_memo(chunk_summaries, status_updates):
    status_updates.append(timestamped("Now synthesizing final memo..."))
    full_text = "\n\n".join(chunk_summaries)
    prompt = f"""You are a professional VC analyst. Based on the summaries below, generate a single, clean investment memo using the exact structure and formatting provided... [prompt truncated for brevity] ...{full_text}"""
    payload = { "contents": [ { "parts": [ { "text": prompt } ] } ] }
    headers = { "Content-Type": "application/json" }
    try:
        response = requests.post(GEMINI_API_URL, json=payload, headers=headers, timeout=120)
        result = response.json()
        status_updates.append(timestamped("Final memo synthesis complete. Sending response..."))
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        status_updates.append(timestamped(f"⚠️ Error synthesizing final memo: {e}"))
        return "⚠️ Memo synthesis failed."

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
    status_updates = []

    status_updates.append(timestamped(f"PDF uploaded. Total pages: {len(doc)}"))
    estimated_sec = max(30, len(doc) * 8)
    estimated_min = estimated_sec // 60
    status_updates.append(timestamped(f"Estimated processing time: {estimated_min} min {estimated_sec % 60} sec"))

    for i, page in enumerate(doc):
        status_updates.append(timestamped(f"Scanning page {i+1} of {len(doc)}..."))
        pix = page.get_pixmap(dpi=300)
        image_path = os.path.join(temp_dir, f"page_{i+1}.png")
        pix.save(image_path)
        image_paths.append(image_path)

    chunk_size = 5
    chunks = [image_paths[i:i+chunk_size] for i in range(0, len(image_paths), chunk_size)]
    status_updates.append(timestamped(f"Chunking complete: {len(chunks)} chunks, {chunk_size} pages per chunk"))
    chunk_summaries = []

    for idx, chunk in enumerate(chunks):
        status_updates.append(timestamped(f"Analyzing chunk {idx+1} of {len(chunks)}..."))
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

    final_memo = synthesize_final_memo(chunk_summaries, status_updates)
    shutil.rmtree(temp_dir)
    return jsonify({ "memo": final_memo, "status_updates": status_updates })

if __name__ == "__main__":
    app.run(debug=True)

