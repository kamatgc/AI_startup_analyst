import os
import google.generativeai as genai
from flask import Flask, request, jsonify

# Load environment variables from a .env file if it exists
# This is a good practice for local development but may not be necessary on Render
# if you use their environment variables feature.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("dotenv not installed. Skipping.")

# Configure the Gemini API client
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("The GOOGLE_API_KEY environment variable is not set.")

genai.configure(api_key=GOOGLE_API_KEY)

# Use the updated way to import HarmCategory and HarmBlockThreshold
# These are now available directly as enums in the google.generativeai module.
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# The model we're using
model = genai.GenerativeModel(
    'gemini-1.5-pro-latest',
    safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    }
)

app = Flask(__name__)

@app.route("/")
def home():
    """A simple home page for the API."""
    return "Gemini Flask API is running!"

@app.route("/chat", methods=["POST"])
def chat():
    """Endpoint for a chat interaction with the Gemini model."""
    data = request.json
    prompt = data.get("prompt")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    try:
        response = model.generate_content(prompt)
        return jsonify({"response": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # When deploying, gunicorn will manage this. This is for local testing.
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
