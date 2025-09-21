import os
import json
import base64
import requests
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
from flask_cors import CORS
import traceback
import time

# Initialize Flask app
# The static_folder is set to '.' so Flask can serve files from the current directory.
app = Flask(__name__, static_folder='.')
CORS(app)

# --- Configuration and Constants ---
# NOTE: Using a placeholder for the API key. In a real-world app, you should
# use environment variables for sensitive information.
API_KEY = "AIzaSyCP1gTahHD0dTMhdQQEO2KlLr7HSti1R5I"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={API_KEY}"
CHUNK_SIZE = 5
UPLOAD_FOLDER = 'temp_uploads'

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(os.path.join(os.getcwd(), UPLOAD_FOLDER))
    print(f"SERVER: Created upload folder at {UPLOAD_FOLDER}")

# --- Helper Functions ---
def pdf_to_base64_images(pdf_file_path):
    """
    Converts each page of a PDF file to a Base64-encoded JPEG image.
    This is a generator function to stream progress.
    """
    try:
        doc = fitz.open(pdf_file_path)
        print(f"SERVER: PDF has {doc.page_count} pages.")
        
        all_images = []
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=200)
            image_buffer = pix.tobytes(output="jpeg", jpg_quality=95)
            all_images.append(base64.b64encode(image_buffer).decode('utf-8'))
        
        doc.close()
        return all_images
    except Exception as e:
        print(f"Error converting PDF to images: {e}")
        return None

def generate_memo_chunk(image_chunk, chunk_num):
    """
    Sends a chunk of images to the Gemini API and returns the generated text.
    Includes retry logic with exponential backoff.
    """
    prompt = f"Analyze these images from a startup pitch deck (Chunk {chunk_num}). Identify key points about the company, its product, market, team, and financial projections. Structure your response as a cohesive section of an investment memo. Include an executive summary for this chunk."

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ] + [
                    {"inlineData": {"mimeType": "image/jpeg", "data": img}} for img in image_chunk
                ]
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    retries = 3
    delay = 1
    
    for attempt in range(retries):
        try:
            print(f"SERVER: Generating memo for chunk {chunk_num}...")
            print(f"SERVER: Attempting API call (Retry {attempt + 1}/{retries})...")
            response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(payload), timeout=120)
            response.raise_for_status()
            
            result = response.json()
            candidate = result.get('candidates')[0] if result.get('candidates') else None
            if not candidate or not candidate.get('content') or not candidate['content'].get('parts'):
                raise ValueError("Invalid API response format")
                
            text = candidate['content']['parts'][0]['text']
            return text
            
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error for chunk {chunk_num}: {http_err}")
            if response.status_code in [429, 500, 503] and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except requests.exceptions.RequestException as req_err:
            print(f"Request error for chunk {chunk_num}: {req_err}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except (ValueError, IndexError) as parse_err:
            print(f"JSON parsing error for chunk {chunk_num}: {parse_err}")
            raise
    
    raise Exception("Failed to get a response from the API after multiple retries.")

def synthesize_final_memo(chunk_summaries):
    """
    Synthesizes the final investment memo from the chunk summaries.
    """
    synthesis_prompt = "You have analyzed a pitch deck in several chunks. The following are the summaries for each chunk. Your task is to synthesize these into a single, comprehensive, and professional investment memo. The final memo should be a polished document covering all aspects of the startup, including a single, overarching executive summary, company overview, market analysis, product details, team, and financial health. Do not mention that the document was created from chunks. Here are the chunks:\n\n" + "\n\n---\n\n".join(chunk_summaries)
    
    payload = {
        "contents": [
            {
                "parts": [{"text": synthesis_prompt}]
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    retries = 3
    delay = 1

    for attempt in range(retries):
        try:
            response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(payload), timeout=180)
            response.raise_for_status()
            
            result = response.json()
            candidate = result.get('candidates')[0] if result.get('candidates') else None
            if not candidate or not candidate.get('content') or not candidate['content'].get('parts'):
                raise ValueError("Invalid API response format")
            
            return candidate['content']['parts'][0]['text']
        
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error during synthesis: {http_err}")
            if response.status_code in [429, 500, 503] and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except requests.exceptions.RequestException as req_err:
            print(f"Request error during synthesis: {req_err}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise
        except (ValueError, IndexError) as parse_err:
            print(f"JSON parsing error during synthesis: {parse_err}")
            raise

    raise Exception("Failed to synthesize memo after multiple retries.")


# --- Routes ---
@app.route('/')
def serve_index():
    print("SERVER: Request received for root URL '/'. Serving index.html...")
    return send_from_directory('.', 'index.html')

@app.route('/ask', methods=['POST'])
def handle_ask():
    print("SERVER: Received POST request at /ask. Checking for file...")
    # This is a streaming response to update the frontend in real-time.
    # The `stream_with_context` is crucial here for long-running processes.
    
    def generate():
        temp_path = None
        try:
            if 'pdf_file' not in request.files:
                print("SERVER: Error: No file part in the request.")
                yield json.dumps({"error": "No file part in the request."}) + '\n'
                return

            file = request.files['pdf_file']
            
            if file.filename == '':
                print("SERVER: Error: No selected file.")
                yield json.dumps({"error": "No selected file."}) + '\n'
                return
            
            print(f"SERVER: File '{file.filename}' received. Saving to temporary path...")
            temp_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(temp_path)
            print(f"SERVER: File saved to '{temp_path}'. Initiating analysis...")

            yield json.dumps({"status": "Processing PDF pages..."}) + '\n'
            all_images = pdf_to_base64_images(temp_path)
            if not all_images:
                print("SERVER: Failed to process PDF file.")
                yield json.dumps({"error": "Failed to process PDF file."}) + '\n'
                return

            chunk_summaries = []
            num_chunks = (len(all_images) + CHUNK_SIZE - 1) // CHUNK_SIZE
            
            for i in range(num_chunks):
                start_index = i * CHUNK_SIZE
                end_index = min(start_index + CHUNK_SIZE, len(all_images))
                chunk_images = all_images[start_index:end_index]
                
                print(f"SERVER: Analyzing chunk {i + 1} of {num_chunks} (pages {start_index + 1} to {end_index})...")
                yield json.dumps({"status": f"Analyzing chunk {i + 1} of {num_chunks}..."}) + '\n'
                chunk_summary = generate_memo_chunk(chunk_images, i + 1)
                chunk_summaries.append(chunk_summary)
                print(f"SERVER: Chunk {i + 1} analysis complete.")

            print("SERVER: All chunks analyzed. Now synthesizing final memo...")
            yield json.dumps({"status": "Synthesizing final investment memo..."}) + '\n'
            final_memo = synthesize_final_memo(chunk_summaries)
            
            print("SERVER: Final memo synthesis complete. Sending response.")
            yield json.dumps({"status": "Analysis complete.", "memo": final_memo}) + '\n'
            
        except Exception as e:
            print(f"SERVER FATAL ERROR: {e}")
            traceback.print_exc()
            yield json.dumps({"error": "An unexpected server error occurred."}) + '\n'
        finally:
            if temp_path and os.path.exists(temp_path):
                print(f"SERVER: Cleaning up temporary file: {temp_path}")
                os.remove(temp_path)
    
    return Response(stream_with_context(generate()), mimetype='application/json')

if __name__ == '__main__':
    # When running locally, you might use app.run().
    # On Render, Gunicorn will handle the server, using the Procfile settings.
    print("SERVER: Application started. Waiting for requests.")
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
