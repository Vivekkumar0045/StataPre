
import sys
import requests
import json
from datetime import datetime
import os
import csv
import re
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Google Generative AI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_API_KEY_HERE":
    print("ERROR: Please set GOOGLE_API_KEY in your .env file")
    sys.exit(1)
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(model_name="gemini-3-flash-preview")

# Ollama configuration for offline mode
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma2"

# Load classification data from JSON
with open("json_data/classify.json", "r", encoding="utf-8") as f:
    CLASSIFY_DATA = json.load(f)

# UTF-8 support for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    
# Create necessary directories
os.makedirs("survey_responses", exist_ok=True)
os.makedirs("prompt_logs", exist_ok=True)

# --- OLLAMA HELPER FUNCTIONS FOR OFFLINE MODE ---

def query_ollama(prompt, model_name="gemma2"):
    """Query Ollama API for offline mode."""
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            print(f"Ollama API error: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        print("Cannot connect to Ollama. Please ensure Ollama is running with 'ollama serve' and the model 'gemma2' is installed.")
        return None
    except Exception as e:
        print(f"Ollama query error: {e}")
        return None

def get_llm_mode():
    """Get the current LLM mode from environment variable."""
    return os.environ.get('LLM_MODE', 'online')

def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def log_prompt(prompt, model_name, purpose):
    """Log all prompts with timestamps"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model_name,
        "purpose": purpose,
        "prompt": prompt
    }
    
    log_filename = f"prompt_logs/prompts_{datetime.now().strftime('%Y%m%d')}.jsonl"
    with open(log_filename, "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

def generate_filename_base(user_query):
    """Generate filename base from query text"""
    # Extract first meaningful word from query
    words = user_query.split()
    name = words[0] if words else "survey"
    
    # Sanitize the name for filename safety
    sanitized = re.sub(r'[^a-zA-Z0-9]', '_', name)
    return sanitized[:50]  # Limit to 50 characters

def save_response(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved response to {filename}")

def extract_json_from_response(response_text):
    """Robust JSON extraction from LLM response"""
    try:
        if '```json' in response_text:
            start = response_text.index('```json') + len('```json')
            end = response_text.index('```', start)
            json_str = response_text[start:end].strip()
        elif '```' in response_text:
            start = response_text.index('```') + len('```')
            end = response_text.index('```', start)
            json_str = response_text[start:end].strip()
        else:
            json_str = response_text.strip()
        
        return json.loads(json_str)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"JSON extraction error: {e}")
        return None

def generate_classification_prompt(user_query):
    prompt = f"""
Classify this survey query: "{user_query}"

You MUST choose exactly one option from each category based on the query content. Pay attention to:
- Mentioned administrative levels
- Sector-specific keywords
- Explicit purposes

Categories and Options:
- level_based: Central, State, District, Village, Urban Local Body, Union Territory
- methodology_based: Census, Sample, Administrative
- purpose_based: Regulatory, Policy Planning, Monitoring & Evaluation, Research & Academic
- sectoral: Agriculture, Health & Nutrition, Education, Labour, Industry, Housing, Social Welfare, Environment
- geographical: Topographical, Geological, Archaeological, Botanical & Zoological
- frequency_based: Decennial, Quinquennial, Annual, Periodic, Ad hoc
- data_collection_method: Quantitative, Qualitative, Mixed Methods

Output JSON format:
{{
  "query": "{user_query}",
  "classifications": {{
    "level_based": "Selected_Option",
    "methodology_based": "Selected_Option",
    "purpose_based": "Selected_Option",
    "sectoral": "Selected_Option",
    "geographical": "Selected_Option",
    "frequency_based": "Selected_Option",
    "data_collection_method": "Selected_Option"
  }}
}}

RULES:
1. Only select options that are explicitly mentioned in the categories
2. Output MUST be valid JSON with no additional text
"""
    return prompt

def get_variable_examples(classifications):
    """Get relevant variable examples from classification data"""
    examples = []
    
    # Get level-based examples
    level = classifications.get("level_based")
    if level and level in CLASSIFY_DATA["level_based"]:
        examples.extend(CLASSIFY_DATA["level_based"][level]["data_variables"][:3])
    
    # Get methodology-based examples
    method = classifications.get("methodology_based")
    if method and method in CLASSIFY_DATA["methodology_based"]:
        examples.extend(CLASSIFY_DATA["methodology_based"][method]["data_variables"][:3])
    
    # Get sectoral examples
    sector = classifications.get("sectoral")
    if sector and sector in CLASSIFY_DATA["sectoral"]:
        sector_data = CLASSIFY_DATA["sectoral"][sector]["data_variables"]
        if isinstance(sector_data, dict):
            # Flatten nested structure
            for sublist in sector_data.values():
                examples.extend(sublist[:2])
        else:
            examples.extend(sector_data[:5])
    
    # Get purpose-based examples
    purpose = classifications.get("purpose_based")
    if purpose and purpose in CLASSIFY_DATA["purpose_based"]:
        examples.extend(CLASSIFY_DATA["purpose_based"][purpose]["data_variables"][:3])
    
    return examples[:15]  # Return top 15 examples

def generate_headings_prompt(user_query, classifications):
    # Get relevant variable examples
    variable_examples = get_variable_examples(classifications)
    
    # Get survey purpose description
    purpose_desc = ""
    purpose = classifications.get("purpose_based")
    if purpose and purpose in CLASSIFY_DATA["purpose_based"]:
        purpose_desc = CLASSIFY_DATA["purpose_based"][purpose]["description"]
    
    # Get methodology description
    method_desc = ""
    method = classifications.get("methodology_based")
    if method and method in CLASSIFY_DATA["methodology_based"]:
        method_desc = CLASSIFY_DATA["methodology_based"][method]["description"]
    
    prompt = f"""
Generate Excel column headings for: "{user_query}"

Classification Context:
{json.dumps(classifications, indent=2, ensure_ascii=False)}

Survey Purpose: {purpose_desc}
Methodology: {method_desc}

RELEVANT VARIABLE EXAMPLES:
{", ".join(variable_examples)}

REQUIREMENTS:
1. Output MUST be a flat JSON array of strings
2. Maximum 15 columns total
3. Structure:
   - Location Identifiers (2-4 columns)
   - Household Identifiers (2-4 columns)
   - Core Subject Columns (5-8 columns)
   - Metadata (1-2 columns)

GUIDELINES:
- Include demographic columns (Age, Gender) when relevant
- Add scheme-specific columns for government programs
- Use India-specific terms: Aadhaar, Ward, Panchayat
- Prefer measurable quantitative fields
- Omit location levels higher than the survey scope
- Include variables that support the survey purpose

Your output: ONLY a JSON array of strings.
"""
    return prompt

def generate_description_prompt(user_query, classifications):
    # Get classification descriptions
    desc_lines = []
    for category, value in classifications.items():
        category_data = CLASSIFY_DATA.get(category, {})
        if value in category_data:
            desc = category_data[value].get("description", "")
            desc_lines.append(f"- {value} ({category.replace('_', ' ').title()}): {desc}")
    
    prompt = f"""
Generate a professional survey description based on:

User Query: "{user_query}"
Classifications: {json.dumps(classifications, indent=2, ensure_ascii=False)}

Description Requirements:
1. Start with "Survey Design: [query]"
2. Incorporate all classification categories naturally
3. Explain the survey's purpose and methodology
4. Mention sector-specific considerations
5. Keep it concise (100-150 words)
6. Use professional government survey terminology

Classification Details:
{"\n".join(desc_lines)}

Do NOT include:
- State/district specific examples unless mentioned in query
- Markdown formatting
- Any JSON structures

Output ONLY the description text.
"""
    return prompt

def query_llm(prompt, model_name="gemini-3-flash-preview", purpose=""):
    # Log the prompt with timestamp
    log_prompt(prompt, model_name, purpose)
    
    # Check mode and query appropriate LLM
    mode = get_llm_mode()
    
    if mode == 'offline':
        print(f"Querying Ollama (Offline Mode) for {purpose}...")
        response_text = query_ollama(prompt, OLLAMA_MODEL)
        if response_text is None:
            raise Exception("Ollama query failed. Please ensure Ollama is running.")
        return response_text
    else:
        # Query the Gemini API (Online Mode)
        print(f"Querying Gemini (Online Mode) for {purpose}...")
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

def generate_survey_design(user_query, model_name="gemini-3-flash-preview", save_output=True):
    # Generate filename base using the prediction model
    filename_base = generate_filename_base(user_query)
    timestamp = datetime.now().strftime("%H%M%S")
    unique_id = "data"
    
    response_data = {
        "timestamp": datetime.now().isoformat(),
        "user_query": user_query,
        "classifications": {},
        "description": "",
        "excel_headings": [],
        "model_used": model_name,
        "files": {}
    }
    
    try:
        # 1. Generate classifications
        print("\nGenerating classifications...")
        classification_prompt = generate_classification_prompt(user_query)
        classification_response = query_llm(
            classification_prompt, 
            model_name,
            purpose="classification"
        )
        classification_data = extract_json_from_response(classification_response)
        
        if not classification_data:
            raise ValueError("Failed to extract valid classification JSON")
            
        classifications = classification_data.get("classifications", {})
        response_data["classifications"] = classifications
        print("\nClassification Results:")
        print(json.dumps(classifications, indent=2, ensure_ascii=False))
        
        # 2. Generate description using LLM
        print("\nGenerating description...")
        description_prompt = generate_description_prompt(user_query, classifications)
        response_data["description"] = query_llm(
            description_prompt, 
            model_name,
            purpose="description"
        ).strip()
        print(f"\n{response_data['description']}")
        with open("survey_responses/data.txt", 'w', newline='', encoding='utf-8') as file:
            file.write(response_data["description"])
            

        # 3. Generate Excel headings
        print("\nGenerating Excel headings...")
        headings_prompt = generate_headings_prompt(user_query, classifications)
        headings_response = query_llm(
            headings_prompt, 
            model_name,
            purpose="headings"
        )
        
        # Extract JSON array from response
        headings_str = headings_response.strip()
        if headings_str.startswith('[') and headings_str.endswith(']'):
            excel_headings = json.loads(headings_str)
        else:
            start = headings_str.find('[')
            end = headings_str.find(']', start) + 1
            if start != -1 and end != 0:
                excel_headings = json.loads(headings_str[start:end])
            else:
                excel_headings = []
        
        response_data["excel_headings"] = excel_headings[:15]
        print("\nGenerated Excel Headings:")
        for i, heading in enumerate(response_data["excel_headings"], 1):
            print(f"{i}. {heading}")

        # 4. Save results
        if save_output:
            json_filename = f"survey_responses/{unique_id}.json"
            save_response(response_data, json_filename)
            response_data["files"]["json"] = json_filename
            
            if response_data["excel_headings"]:
                csv_filename = f"survey_responses/{unique_id}.csv"
                with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(response_data["excel_headings"])
                    for _ in range(5):
                        writer.writerow([''] * len(response_data["excel_headings"]))
                response_data["files"]["csv"] = csv_filename
                print(f"\nCreated CSV template: {csv_filename}")

        print("\n" + "="*50)
        print(f"SURVEY DESIGN COMPLETE FOR: '{user_query}'")
        print(f"Files saved with base name: {unique_id}")
        print("="*50)

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        response_data["error"] = error_msg
        
        # Save error information
        if save_output:
            error_filename = f"survey_responses/error_{unique_id}.json"
            save_response(response_data, error_filename)
        
    return response_data

def main():
    user_query = input("Enter your survey query: ").strip()
    generate_survey_design(user_query)
    

if __name__ == "__main__":
    main()