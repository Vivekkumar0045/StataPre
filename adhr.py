import json
import os
import google.generativeai as genai
from PIL import Image

# Configure Google Generative AI
# Get API key from environment variable (set by app.py)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("ERROR: GOOGLE_API_KEY not found. Please ensure app.py is setting it from Streamlit secrets.")
    exit(1)
genai.configure(api_key=GOOGLE_API_KEY)
# Use Gemini 3 Pro with vision capabilities
vision_model = genai.GenerativeModel(model_name="gemini-3-pro-preview")

def extract_text_from_image(image_path):
    """Use Gemini 2.0 Pro vision to extract and structure Aadhaar card data directly from image."""
    try:
        # Open image
        img = Image.open(image_path)
        
        # Create prompt for Gemini to extract Aadhaar data
        prompt = """
You are an expert at extracting structured data from Aadhaar card images.

Analyze this Aadhaar card image and extract the following information:
- name: full name of the person
- dob: date of birth in DD/MM/YYYY format
- gender: Male/Female/Other
- aadhaar_number: exactly 12-digit Aadhaar number
- address: complete postal address in English

IMPORTANT:
- The Aadhaar card typically has: name at top, followed by date of birth, gender, and address at bottom
- The 12-digit Aadhaar number can appear anywhere on the card
- Clean and correct any OCR errors
- For address, remove any gibberish and present it in proper order

Return ONLY a valid JSON object with these exact keys. No explanations, no markdown formatting.
"""
        
        # Send image and prompt to Gemini
        response = vision_model.generate_content([prompt, img])
        
        # Extract and clean the response
        raw_output = response.text.strip()
        
        # Remove markdown code blocks if present
        cleaned_output = raw_output.strip().strip("`")
        cleaned_output = cleaned_output.replace("```json", "").replace("```", "").strip()
        if cleaned_output.lower().startswith("json"):
            cleaned_output = cleaned_output[4:].strip()
        
        # Parse JSON
        data = json.loads(cleaned_output)
        
        print("✅ Gemini Vision extracted data successfully")
        return data
        
    except Exception as e:
        print(f"❌ Gemini Vision extraction failed: {e}")
        return {}

def extract_and_process(image_path):
    print(f"📷 Processing Aadhaar image with Gemini Vision: {image_path}")
    data = extract_text_from_image(image_path)
    
    if not data:
        print("❌ No data extracted from image.")
        return {}
    
    print("\n✅ Extracted Aadhaar Data:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    with open("aadhaar_output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        print("📁 Saved to: aadhaar_output.json")
    
    return data

if __name__ == "__main__":
    IMAGE_PATH = input("Enter image path: ")
    extract_and_process(IMAGE_PATH)


