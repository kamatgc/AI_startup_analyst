from flask import Flask, request, Response, render_template, stream_with_context
import os
import fitz
import tempfile
import shutil
import requests
import base64
from datetime import datetime
import json

app = Flask(__name__, template_folder="templates", static_folder="static")
API_KEY = "AIzaSyAcPLSUgM9ZarS3D0CW0DmCzPLySBenQeU"
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={API_KEY}"

def timestamped(msg):
    return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"

def stream_status(uploaded_file):
    temp_dir = tempfile.mkdtemp()
    pdf_path = os.path.join(temp_dir, uploaded_file.filename)
    uploaded_file.save(pdf_path)

    doc = fitz.open(pdf_path)
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
    prompt = f"""You are a professional VC analyst. Based on the summaries below, generate a single, clean investment memo using the exact structure and formatting provided... [prompt truncated] ...{full_text}"""
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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    uploaded_file = request.files["file"]
    return Response(stream_with_context(stream_status(uploaded_file)), content_type='text/event-stream')

if __name__ == "__main__":
    app.run(debug=True)

