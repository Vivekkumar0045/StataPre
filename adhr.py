import pytesseract
import cv2
import requests
import json
import re
import os
import google.generativeai as genai

# Configure Google Generative AI
# Get API key from environment variable (set by app.py)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("ERROR: GOOGLE_API_KEY not found. Please ensure app.py is setting it from Streamlit secrets.")
    exit(1)
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(model_name="gemini-3-flash-preview")

def extract_text_from_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    
    # Convert to grayscale and apply adaptive threshold for better OCR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 2
    )

    # Run Tesseract OCR with English and Hindi support
    text = pytesseract.image_to_string(thresh, lang='eng')
    print(text)
    return text

def send_to_llm_for_json(raw_text):
    prompt = f"""
You are an intelligent assistant that extracts structured Aadhaar card data from OCR output.

Clean and correct the text where possible, especially the address. Return only a well-formed JSON with:
- name: full name
- dob: date of birth in DD/MM/YYYY format
- gender: Male/Female/Other
- aadhaar_number: exactly 12-digit number
- address: cleaned postal address in English (remove gibberish, fix order)

usually in aadhar card name appears at start followed by date of birth then sex and at last address . 
and addahr number (12 digit number) can be anywhere 
so use this info 

OCR Text:
\"\"\"
{raw_text}
\"\"\"

Output only the JSON. No explanations, no markdown.
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "gemma3n",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        response_json = response.json()
        raw_output = response_json.get("response", "")

        # Clean output (remove markdown/code blocks if present)
        cleaned_output = raw_output.strip().strip("`")
        cleaned_output = cleaned_output.replace("```json", "").replace("```", "").strip()
        if cleaned_output.lower().startswith("json"):
            cleaned_output = cleaned_output[4:].strip()

        # Parse JSON
        return json.loads(cleaned_output)

    except Exception as e:
        print("❌ LLM processing failed:", e)
        print("Response content:\n", raw_output if 'raw_output' in locals() else "")
        return {}

def extract_and_process(image_path):
    print(f"📷 Reading Aadhaar image: {image_path}")
    text = extract_text_from_image(image_path)
    if not text.strip():
        print("❌ No text found via OCR.")
        return {}
    
    print("🧠 Sending OCR text to LLM (Gemini)...")
    data = send_to_llm_for_json(text)

    print("\n✅ Extracted Aadhaar Data:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    with open("aadhaar_output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        print("📁 Saved to: aadhaar_output.json")

if __name__ == "__main__":
    IMAGE_PATH =  input("Enter image path : ")
    extract_and_process(IMAGE_PATH)


