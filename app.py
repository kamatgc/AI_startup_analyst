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
    prompt = f"""The memo MUST follow this exact structure... [truncated for brevity] ...The summaries to be synthesized are below:\n\n{full_text}"""
    payload = { "contents": [ { "parts": [ { "text": prompt } ] } ] }
    headers = { "Content-Type": "application/json" }
    response = requests.post(GEMINI_API_URL, json=payload, headers=headers)
    result = response.json()
    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
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

    chunks = [image_paths[i:i+5] for i in range(0, len(image_paths), 5)]
    chunk_summaries = []

    for idx, chunk in enumerate(chunks):
        parts = [{"text": f"You are an expert VC analyst... Chunk {idx+1} of {len(chunks)}"}]
        for img_path in chunk:
            with open(img_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
                parts.append({ "inline_data": { "mime_type": "image/png", "data": encoded } })
        payload = { "contents": [ { "parts": parts } ] }
        headers = { "Content-Type": "application/json" }
        response = requests.post(GEMINI_API_URL, json=payload, headers=headers)
        result = response.json()
        try:
            chunk_text = result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            chunk_text = f"⚠️ Error parsing chunk {idx+1}: {e}"
        chunk_summaries.append(chunk_text.strip())

    final_memo = synthesize_final_memo(chunk_summaries)
    shutil.rmtree(temp_dir)
    return jsonify({ "memo": final_memo })

if __name__ == "__main__":
    app.run(debug=True)

