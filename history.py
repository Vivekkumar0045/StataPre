import streamlit as st
import pandas as pd
import json
import os
import requests
import time
from datetime import datetime
import hashlib
import shutil
import webbrowser
from content import HTML_TEMPLATE # Import the HTML template
import plotly.express as px
import google.generativeai as genai
from supabase import create_client, Client
import ds_r1 , adhr
import random 



# Configure Google Generative AI
# Use Streamlit secrets for API key
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("Please set GOOGLE_API_KEY in .streamlit/secrets.toml file")
    st.info("Create a .streamlit/secrets.toml file with: GOOGLE_API_KEY = 'your-api-key-here'")
    st.stop()

if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_API_KEY_HERE":
    st.error("Please set a valid GOOGLE_API_KEY in .streamlit/secrets.toml file")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(model_name="gemini-3-flash-preview")

# Set API key in environment for child modules
os.environ['GOOGLE_API_KEY'] = GOOGLE_API_KEY

# Initialize Supabase client
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except (KeyError, FileNotFoundError):
    st.error("Please set SUPABASE_URL and SUPABASE_KEY in .streamlit/secrets.toml file")
    st.stop()

# Ollama configuration for offline mode
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma2"

# --- Import your custom functions ---
# Ensure ds_r1.py and adhr.py are in the same directory as this script.
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import ds_r1
    import adhr
    generate_survey_design = ds_r1.generate_survey_design
    extract_and_process = adhr.extract_and_process
except ImportError as e:
    st.error(f"Import error: {e}")
    # This allows the app to run without the files for initial setup.
    # A proper error will be shown if the user tries to generate a survey.
    def generate_survey_design(query):
        st.error("`ds_r1.py` not found. Please add it to the project directory.")
        return None
    def extract_and_process(image_path):
        st.error("`adhr.py` not found. Please add it to the project directory.")
        return None

# --- PROJECT SETUP ---
os.makedirs("survey_responses", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("survey_jsons", exist_ok=True)
os.makedirs("shareable_forms", exist_ok=True)
os.makedirs("survey_scripts", exist_ok=True) # Directory for new script format
DB_NAME = "survey_portal.db"
CONFIG_FILE = "json_data/config.json"
LANG_FILE = "json_data/lang.json"

# --- LOCALIZATION (TRANSLATION) ---
def load_translations():
    """Loads translations from the lang.json file."""
    try:
        with open(LANG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default empty dict to prevent crash
        return {"en": {}, "hi": {}}
    except json.JSONDecodeError:
        # Return default empty dict if JSON is invalid
        return {"en": {}, "hi": {}}

TRANSLATIONS = load_translations()

# --- OLLAMA HELPER FUNCTIONS FOR OFFLINE MODE ---

def query_ollama(prompt, model_name=None):
    """Query Ollama API for offline mode."""
    # Use selected model from session state, fallback to gemma3:latest
    if model_name is None:
        model_name = st.session_state.get('ollama_model', 'gemma3:latest')
    
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
            st.error(f"Ollama API error: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to Ollama. Please ensure Ollama is running with 'ollama serve' and the model '{model_name}' is installed.")
        return None
    except Exception as e:
        st.error(f"Ollama query error: {e}")
        return None

def generate_with_llm(prompt):
    """Generate content using the selected LLM (online or offline)."""
    mode = st.session_state.get('llm_mode', 'online')
    
    if mode == 'offline':
        return query_ollama(prompt)
    else:
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            st.error(f"Gemini API error: {e}")
            return None

# --- 1. CONFIG AND DATABASE MANAGEMENT ---

def hash_password(password):
    """Hashes the password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def init_coins():
    """Initialize coins in session state if not exists."""
    if 'user_coins' not in st.session_state:
        st.session_state.user_coins = 0

def add_coins(amount):
    """Add coins to user's balance."""
    if 'user_coins' not in st.session_state:
        st.session_state.user_coins = 0
    st.session_state.user_coins += amount

def deduct_coins(amount):
    """Deduct coins from user's balance."""
    if 'user_coins' not in st.session_state:
        st.session_state.user_coins = 0
    if st.session_state.user_coins >= amount:
        st.session_state.user_coins -= amount
        return True
    return False

def get_coins():
    """Get current coin balance."""
    return st.session_state.get('user_coins', 0)

def init_config():
    """Creates a default config file if it doesn't exist."""
    # Initialize LLM mode if not already set
    if 'llm_mode' not in st.session_state:
        st.session_state.llm_mode = 'online'
    
    # Initialize coins
    init_coins()
    
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "admins": [
                {
                    "username": "admin",
                    "password_hash": hash_password("123")
                },
                {
                    "username": "admin user",
                    "password_hash": hash_password("786")
                }
            ]
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=4)

def load_config():
    """Loads the configuration from the JSON file."""
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def init_db():
    """    Initializes the database tables in Supabase.
    Tables should be created in Supabase dashboard with the following schema:
    - surveys: id (int8, PK), title (text), description (text), status (text), json_path (text), created_at (timestamp)
    - users: id (int8, PK), name (text), username (text, unique), password (text), role (text), language (text), contact (text), created_at (timestamp)
    - respondents: id (int8, PK), survey_id (int8), name (text), dob (text), gender (text), aadhaar_number (text, unique), address (text), created_at (timestamp), start_time (text), end_time (text), device_info (text), geo_latitude (text), geo_longitude (text), ip_address (text), ip_city (text), ip_country (text)
    - answers: id (int8, PK), respondent_id (int8), question (text), answer (text), created_at (timestamp)
    """
    # Tables are created in Supabase dashboard
    pass

# --- User and Survey CRUD Functions ---
def add_user(name, username, password, language, contact):
    try:
        data = {
            "name": name,
            "username": username,
            "password": hash_password(password),
            "role": "Enumerator",
            "language": language,
            "contact": contact
        }
        supabase.table("users").insert(data).execute()
        return True
    except Exception as e:
        print(f"Error adding user: {e}")
        return False

def get_user(username):
    try:
        response = supabase.table("users").select("*").eq("username", username).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def add_survey(title, description, status, json_path):
    """Adds a new survey to the database and returns its ID."""
    try:
        data = {
            "title": title,
            "description": description,
            "status": status,
            "json_path": json_path
        }
        response = supabase.table("surveys").insert(data).execute()
        if response.data:
            return response.data[0]['id']
        return None
    except Exception as e:
        print(f"Error adding survey: {e}")
        return None

def get_all_surveys():
    try:
        response = supabase.table("surveys").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error getting surveys: {e}")
        return []
    
def update_survey_status(survey_id, status):
    try:
        supabase.table("surveys").update({"status": status}).eq("id", survey_id).execute()
    except Exception as e:
        print(f"Error updating survey status: {e}")

def delete_survey(survey_id):
    try:
        supabase.table("surveys").delete().eq("id", survey_id).execute()
    except Exception as e:
        print(f"Error deleting survey: {e}")
    
def get_all_users():
    try:
        response = supabase.table("users").select("id, name, username, role, language, contact").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error getting users: {e}")
        return []

def add_respondent(survey_id, name, dob, gender, aadhaar, address):
    try:
        data = {
            "survey_id": survey_id,
            "name": name,
            "dob": dob,
            "gender": gender,
            "aadhaar_number": aadhaar,
            "address": address
        }
        response = supabase.table("respondents").insert(data).execute()
        if response.data:
            return response.data[0]['id']
        return None
    except Exception as e:
        # If aadhaar already exists, get the existing respondent id
        try:
            response = supabase.table("respondents").select("id").eq("aadhaar_number", aadhaar).execute()
            if response.data:
                return response.data[0]['id']
        except:
            pass
        print(f"Error adding respondent: {e}")
        return None

def save_answers(respondent_id, answers_dict):
    try:
        answers_list = [
            {
                "respondent_id": respondent_id,
                "question": question,
                "answer": str(answer)
            }
            for question, answer in answers_dict.items()
        ]
        supabase.table("answers").insert(answers_list).execute()
    except Exception as e:
        print(f"Error saving answers: {e}")

def get_survey_results(survey_id):
    """
    Fetches all results from Supabase and returns a single, combined DataFrame.
    """
    try:
        # Get respondents for this survey
        respondents_response = supabase.table("respondents").select("*").eq("survey_id", survey_id).execute()
        
        if not respondents_response.data:
            return pd.DataFrame()
        
        respondents_df = pd.DataFrame(respondents_response.data)
        respondent_ids = respondents_df['id'].tolist()
        
        # Get answers for these respondents
        answers_response = supabase.table("answers").select("*").in_("respondent_id", respondent_ids).execute()
        
        if not answers_response.data:
            return respondents_df
        
        answers_df = pd.DataFrame(answers_response.data)
        
        # Pivot answers
        pivoted_answers_df = answers_df.pivot(index='respondent_id', columns='question', values='answer').reset_index()
        results_df = pd.merge(respondents_df, pivoted_answers_df, left_on='id', right_on='respondent_id', how='left')
        return results_df
    except Exception as e:
        print(f"Error getting survey results: {e}")
        return pd.DataFrame()


# --- 2. CORE BACKEND FUNCTIONS ---
def create_unique_survey_name(query: str) -> str:
    base_name = query.split()[0].lower().strip().replace("'", "")
    return f"{base_name}_{int(time.time())}"

def create_survey_json_iteratively(survey_name: str):
    try:
        with open(f"survey_responses/{survey_name}.txt", "r", encoding='utf-8') as f:
            survey_description = f.read().strip()
        df = pd.read_csv(f"survey_responses/{survey_name}.csv")
    except FileNotFoundError as e:
        st.error(f"Error: Design file not found: {e}.")
        return None, None

    survey_questions = []
    progress_bar = st.progress(0, text="Initializing LLM...")
    for i, header in enumerate(df.columns):
        progress_text = f"Generating question for '{header}'... ({i+1}/{len(df.columns)})"
        st.toast(progress_text)
        progress_bar.progress((i + 1) / len(df.columns), text=progress_text)

        try:
            prompt = f"""Given a survey about '{survey_description}', generate a JSON object for a single survey question based on the data field '{header}'. The JSON object must have ONLY three keys: "question", "description", and "type" (choose from 'text', 'yes/no', or 'rating_1_10')."""
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON from markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            question_json = json.loads(response_text)

            if all(k in question_json for k in ["question", "description", "type"]):
                survey_questions.append(question_json)
            else:
                st.warning(f"LLM returned incomplete data for '{header}'. Using a default question.")
                survey_questions.append({"question": header.replace('_', ' ').title(), "description": "Please provide your input for this question.", "type": "text"})
        except Exception as e:
            st.error(f"Failed to connect to Google Gemini API. Error: {e}")
            return None, None
        except (json.JSONDecodeError, Exception) as e:
            st.warning(f"Could not generate a valid question for '{header}': {e}. Using a default question.")
            survey_questions.append({"question": header.replace('_', ' ').title(), "description": "Please provide your input for this question.", "type": "text"})

    progress_bar.empty()
    json_path = os.path.join("survey_jsons", f"{survey_name}.json")
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(survey_questions, f, indent=2, ensure_ascii=False)
    return json_path, survey_description

def create_conversational_script(survey_id, survey_name):
    """Generates a conversational script and saves it using the survey ID."""
    original_json_path = os.path.join("survey_jsons", f"{survey_name}.json")
    script_json_path = os.path.join("survey_scripts", f"script_{survey_id}.json")

    try:
        with open(original_json_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
    except Exception as e:
        st.error(f"Could not read original survey JSON: {e}")
        return None, None

    script = []
    progress_bar = st.progress(0, text="Initializing script generation...")
    for i, question_data in enumerate(questions):
        progress_text = f"Generating script for question {i+1}/{len(questions)}..."
        st.toast(progress_text)
        progress_bar.progress((i + 1) / len(questions), text=progress_text)

        try:
            prompt = f"""
            You are creating a single step for a conversational survey. Based on the following question details, create a JSON object with three keys:
            1. "say": A friendly, conversational way to ask this question.
            2. "explain": A slightly more detailed explanation of the question if the user asks for one.
            3. "question_key": The original question text to use as a key for saving the answer.
            The final output must be a single, valid JSON object for this one question.
            Question Details: {json.dumps(question_data)}
            """
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON from markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            script_part = json.loads(response_text)

            if all(k in script_part for k in ["say", "explain", "question_key"]):
                script.append(script_part)
            else:
                raise ValueError("LLM response did not contain required keys.")
        except (ValueError, json.JSONDecodeError, Exception) as e:
            st.warning(f"Failed to generate script for a question ({e}). Using default format.")
            script.append({
                "say": question_data['question'],
                "explain": question_data.get('description', 'No further details.'),
                "question_key": question_data['question']
            })

    progress_bar.empty()
    with open(script_json_path, "w", encoding='utf-8') as f:
        json.dump(script, f, indent=2, ensure_ascii=False)

    return script_json_path, script

# --- Shareable Form Generation (HTML Only) ---
def generate_html_form(survey_details):
    """Generates a standalone HTML form for a survey."""
    survey_id = survey_details['id']
    json_path = survey_details['json_path']

    form_dir = os.path.join("shareable_forms", f"survey_{survey_id}")
    os.makedirs(form_dir, exist_ok=True)
    html_path = os.path.join(form_dir, "form.html")

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            survey_questions = json.load(f)
    except Exception as e:
        st.error(f"Could not read survey JSON: {e}")
        return None

    html_content = HTML_TEMPLATE.format(
        survey_title=survey_details['title'],
        survey_description=survey_details['description'],
        survey_questions_json=json.dumps(survey_questions),
        survey_id=survey_id
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return html_path


# --- 3. STREAMLIT UI ---
def render_login_page():
    """Displays the main login and signup page."""
    t = TRANSLATIONS.get('en', {})
    st.title(t.get("login_page_title", "Welcome"))

    admin_tab, user_tab, signup_tab = st.tabs([
        t.get("admin_login_tab", "Admin Login"),
        t.get("user_login_tab", "User Login"),
        t.get("user_signup_tab", "User Signup")
    ])

    with admin_tab:
        with st.form("admin_login_form"):
            st.subheader(t.get("admin_login_tab", "Admin Login"))
            admin_user = st.text_input(label=t.get("username_label", "Username"), key="admin_user")
            admin_pass = st.text_input(label=t.get("password_label", "Password"), type="password", key="admin_pass")
            if st.form_submit_button(t.get("login_button", "Login")):
                config = load_config()
                admins = config.get("admins", [])
                logged_in_successfully = False
                for admin_config in admins:
                    if admin_user == admin_config.get("username") and hash_password(admin_pass) == admin_config.get("password_hash"):
                        st.session_state.logged_in = True
                        st.session_state.role = "admin"
                        st.session_state.username = admin_config.get("username")
                        st.session_state.language = "en"
                        logged_in_successfully = True
                        st.rerun()
                if not logged_in_successfully:
                    st.error(t.get("invalid_credentials_error", "Invalid credentials."))

    with user_tab:
        with st.form("user_login_form"):
            st.subheader(t.get("user_login_tab", "User Login"))
            username = st.text_input(label=t.get("username_label", "Username"), key="user_login_username")
            user_pass = st.text_input(label=t.get("password_label", "Password"), type="password", key="user_login_pass")
            if st.form_submit_button(t.get("login_button", "Login")):
                user = get_user(username)
                if user and user['password'] == hash_password(user_pass):
                    st.session_state.logged_in = True
                    st.session_state.role = user['role']
                    st.session_state.username = user['username']
                    st.session_state.language = user['language']
                    st.rerun()
                else:
                    st.error(t.get("invalid_credentials_error", "Invalid credentials."))

    with signup_tab:
        with st.form("signup_form", clear_on_submit=True):
            st.subheader(t.get("user_signup_tab", "User Signup"))
            name = st.text_input(t.get("signup_name_label", "Full Name"))
            username = st.text_input(t.get("signup_username_label", "Username"))
            password = st.text_input(t.get("signup_password_label", "Password"), type="password")
            language = st.selectbox(t.get("signup_language_label", "Language"), options=['en', 'hi'], format_func=lambda x: "English" if x == 'en' else "हिंदी")
            contact = st.text_input(t.get("contact_label", "Contact"))
            if st.form_submit_button(t.get("signup_button", "Sign Up")):
                if add_user(name, username, password, language, contact):
                    st.success(t.get("signup_success_message", "Success!"))
                else:
                    st.error(t.get("signup_user_exists_error", "User exists."))

def render_dashboard(t):
    st.title(f"🏠 {t['nav_dashboard']}")
    st.markdown(t['dashboard_welcome'])
    
    # LLM Mode Selection (Admin Only)
    if st.session_state.get('role') == 'admin':
        st.markdown("""
        <style>
        .mode-container {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .mode-title {
            color: white;
            font-size: 18px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 15px;
        }
        .mode-status {
            color: #ffd700;
            font-size: 14px;
            text-align: center;
            margin-top: 10px;
            animation: fadeIn 0.5s;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .stButton button {
            width: 100%;
            transition: all 0.3s ease;
        }
        .stButton button:hover {
            transform: scale(1.05);
        }
        </style>
        """, unsafe_allow_html=True)
        
        # LLM Mode Toggle
        st.markdown('<div class="mode-container">', unsafe_allow_html=True)
        st.markdown('<div class="mode-title">🤖 AI Mode Selection</div>', unsafe_allow_html=True)
        
        col_mode1, col_mode2 = st.columns(2)
        
        current_mode = st.session_state.get('llm_mode', 'online')
        
        with col_mode1:
            if st.button("🌐 Online (Gemini)", 
                        type="primary" if current_mode == 'online' else "secondary",
                        use_container_width=True):
                st.session_state.llm_mode = 'online'
                os.environ['LLM_MODE'] = 'online'
                st.success("✅ Switched to Online Mode (Gemini API)")
                time.sleep(0.5)
                st.rerun()
        
        with col_mode2:
            if st.button("🔒 Offline & Secure (Ollama)", 
                        type="primary" if current_mode == 'offline' else "secondary",
                        use_container_width=True):
                st.session_state.llm_mode = 'offline'
                os.environ['LLM_MODE'] = 'offline'
                st.success("✅ Switched to Offline & Secure Mode (Ollama)")
                time.sleep(0.5)
                st.rerun()
        
        # Model selection for offline mode
        if current_mode == 'offline':
            st.markdown("### 🎯 Select Ollama Model")
            available_models = [
                "gemma3:latest",
                "gemma3:12b",
                "gemma3:27b",
                "llama3.1:latest",
                "llama3:latest",
                "deepseek-r1:latest",
                "mistral:latest",
                "command-r7b:latest",
                "tinyllama:1.1b",
                "wizardcoder:latest",
                "deepseek-coder:latest",
                "gemma3n:latest",
                "embeddinggemma:latest"
            ]
            
            # Initialize selected model if not exists
            if 'ollama_model' not in st.session_state:
                st.session_state.ollama_model = 'gemma3:latest'
            
            selected_model = st.selectbox(
                "Choose your model:",
                options=available_models,
                index=available_models.index(st.session_state.ollama_model),
                key="model_selector"
            )
            
            if selected_model != st.session_state.ollama_model:
                st.session_state.ollama_model = selected_model
                os.environ['OLLAMA_MODEL'] = selected_model
                st.success(f"✅ Model changed to: {selected_model}")
                st.rerun()
        
        # Display current mode status with animation
        mode_emoji = "🌐" if current_mode == 'online' else "🔒"
        mode_text = "Online (Gemini API)" if current_mode == 'online' else f"Offline & Secure ({st.session_state.get('ollama_model', 'gemma3:latest')})"
        st.markdown(f'<div class="mode-status">{mode_emoji} Current Mode: {mode_text}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
    
    try:
        # Count surveys
        surveys_response = supabase.table("surveys").select("id", count='exact').execute()
        total_surveys = len(surveys_response.data) if surveys_response.data else 0
        
        # Count enumerators
        users_response = supabase.table("users").select("id", count='exact').eq("role", "Enumerator").execute()
        total_users = len(users_response.data) if users_response.data else 0
        
        # Count respondents
        respondents_response = supabase.table("respondents").select("id", count='exact').execute()
        completed_respondents = len(respondents_response.data) if respondents_response.data else 0
    except Exception as e:
        st.error(f"Error loading dashboard metrics: {e}")
        total_surveys = 0
        total_users = 0
        completed_respondents = 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric(t['metric_total_surveys'], total_surveys)
    col2.metric(t['metric_registered_enumerators'], total_users)
    col3.metric(t['metric_surveys_completed'], completed_respondents)

def render_store(t):
    """Render the rewards store."""
    st.title("🏪 Rewards Store")
    
    # Display current balance prominently
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.metric("Your Coins", f"🪙 {get_coins()}")
    
    st.markdown("---")
    st.subheader("Available Rewards")
    
    # Define rewards catalog
    rewards = [
        {
            "name": "Railway Ticket Discount (10%)",
            "description": "Get 10% off on your next railway ticket booking",
            "icon": "🚂",
            "cost": 500,
            "code": "RAIL10"
        },
        {
            "name": "Railway Ticket Discount (20%)",
            "description": "Get 20% off on your next railway ticket booking",
            "icon": "🚄",
            "cost": 800,
            "code": "RAIL20"
        },
        {
            "name": "JEE Application Fee Discount",
            "description": "₹500 off on JEE application fee",
            "icon": "📚",
            "cost": 600,
            "code": "JEE500"
        },
        {
            "name": "NEET Application Fee Discount",
            "description": "₹500 off on NEET application fee",
            "icon": "🩺",
            "cost": 600,
            "code": "NEET500"
        },
        {
            "name": "Petrol Pump Discount (5%)",
            "description": "Get 5% discount at participating petrol pumps",
            "icon": "⛽",
            "cost": 450,
            "code": "FUEL5"
        },
        {
            "name": "Petrol Pump Discount (10%)",
            "description": "Get 10% discount at participating petrol pumps",
            "icon": "⛽",
            "cost": 750,
            "code": "FUEL10"
        },
        {
            "name": "Government Forms Bundle",
            "description": "₹200 off on various government form applications",
            "icon": "📋",
            "cost": 400,
            "code": "GOVT200"
        },
    ]
    
    # Display rewards in a grid
    for i in range(0, len(rewards), 2):
        cols = st.columns(2)
        for idx, col in enumerate(cols):
            if i + idx < len(rewards):
                reward = rewards[i + idx]
                with col:
                    with st.container(border=True):
                        st.markdown(f"### {reward['icon']} {reward['name']}")
                        st.write(reward['description'])
                        st.markdown(f"**Cost:** 🪙 {reward['cost']} coins")
                        
                        if st.button(f"Redeem", key=f"redeem_{i+idx}"):
                            if deduct_coins(reward['cost']):
                                st.success(f"✅ Redeemed successfully! Your code: **{reward['code']}**")
                                st.info("💡 Note this code down and use it during checkout/application")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(f"❌ Insufficient coins! You need {reward['cost']} coins but have {get_coins()} coins.")
    
    st.markdown("---")
    st.info("💡 **Tip:** Complete more surveys to earn coins and unlock rewards!")

def render_user_dashboard(t):
    # Display coins at the top right (only for non-admin users)
    if st.session_state.get('role') != 'admin':
        col1, col2 = st.columns([3, 1])
        with col1:
            st.title(f"👋 {t['user_dashboard_welcome']}, {st.session_state.username}!")
        with col2:
            st.markdown("###")
            st.metric("", f"🪙 {get_coins()} coins")
    else:
        st.title(f"👋 {t['user_dashboard_welcome']}, {st.session_state.username}!")
    st.markdown("---")
    deployed_surveys = [s for s in get_all_surveys() if s['status'] == 'Deployed']
    st.metric(t['metric_available_surveys'], len(deployed_surveys))
    st.markdown("---")
    st.subheader("Quick Actions")
    st.info("Navigate to 'Take a Survey' from the sidebar to begin.")

def render_survey_management(t):
    st.title(f"📝 {t['nav_survey_management']}")

    # --- STAGE 1: CSV Editing ---
    if st.session_state.get('csv_editing_stage', False):
        st.subheader("Step 2: Review and Edit Survey Columns")
        st.info("Add, rename, or delete columns before generating questions. To delete, select rows and press the 'Delete' key.")
        edited_df = st.data_editor(st.session_state.editable_df, num_rows="dynamic")
        st.session_state.editable_df = edited_df
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            with st.form("rename_column_form"):
                st.subheader("Rename Column")
                old_name = st.selectbox("Column to Rename", options=st.session_state.editable_df.columns)
                new_name = st.text_input("New Name")
                if st.form_submit_button("Rename"):
                    if old_name and new_name:
                        df = st.session_state.editable_df.rename(columns={old_name: new_name})
                        st.session_state.editable_df = df
                        st.rerun()
        with col2:
            with st.form("add_column_form"):
                st.subheader("Add New Column")
                add_name = st.text_input("New Column Name")
                if st.form_submit_button("Add"):
                    if add_name:
                        df = st.session_state.editable_df
                        df[add_name] = ""
                        st.session_state.editable_df = df
                        st.rerun()

        st.markdown("---")
        if st.button("✅ Confirm Columns & Generate Questions", type="primary"):
            final_df = st.session_state.editable_df
            survey_name = st.session_state.survey_name
            final_df.to_csv(f"survey_responses/{survey_name}.csv", index=False)
            with st.spinner("Building survey questions with AI..."):
                json_path, description = create_survey_json_iteratively(survey_name)

            if json_path:
                with st.spinner("Saving initial survey draft..."):
                    new_survey_id = add_survey(
                        title=st.session_state.query.split('.')[0],
                        description=description,
                        status='Draft',
                        json_path=json_path
                    )
                st.session_state.survey_id = new_survey_id
                st.session_state.json_path = json_path
                st.session_state.description = description
                st.session_state.csv_editing_stage = False
                st.session_state.question_review_stage = True
                st.rerun()

    # --- STAGE 2: Question Review and Script Generation ---
    elif st.session_state.get('question_review_stage', False):
        st.subheader(f"Step 3: Review Questions for Survey ID: {st.session_state.survey_id}")
        json_path = st.session_state.json_path
        with open(json_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Original Questions")
            with st.container(height=400):
                for q in questions:
                    with st.expander(q['question']):
                        st.write(f"**Description:** {q['description']}")
                        st.write(f"**Type:** {q['type']}")

        with col2:
            st.markdown("#### Conversational Script")
            if 'script_data' not in st.session_state:
                if st.button("Generate Conversational Script"):
                    with st.spinner("Generating script... this may take a moment."):
                        script_path, script_data = create_conversational_script(
                            survey_id=st.session_state.survey_id,
                            survey_name=st.session_state.survey_name
                        )
                        if script_path and script_data:
                            # Script saved locally in survey_scripts folder
                            st.session_state.script_path = script_path
                            st.session_state.script_data = script_data
                            st.success(f"Script saved to {script_path}")
                            st.rerun()
            else:
                with st.container(height=400):
                    for s in st.session_state.script_data:
                        with st.expander(s['say']):
                            st.info(f"**If user needs help:** {s['explain']}")
                            st.caption(f"Original Question Key: {s['question_key']}")

        st.markdown("---")
        st.subheader("Finalize Survey")
        if st.button("✅ Finish and Return to List", type="primary"):
            st.success("🎉 Survey creation process complete!")
            for key in ['csv_editing_stage', 'editable_df', 'survey_name', 'query', 'question_review_stage', 'json_path', 'description', 'script_path', 'script_data', 'survey_id']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    # --- STAGE 0: Initial Creation Form ---
    else:
        with st.expander(f"➕ {t['create_new_survey_expander']}", expanded=True):
            with st.form("survey_creation_form"):
                query = st.text_area(t['generate_survey_prompt'], height=150)
                if st.form_submit_button(t['generate_survey_button']):
                    if query.strip():
                        with st.spinner("Generating Survey Blueprint..."):
                            generate_survey_design(query)
                        survey_name = create_unique_survey_name(query)
                        try:
                            os.rename("survey_responses/data.csv", f"survey_responses/{survey_name}.csv")
                            os.rename("survey_responses/data.txt", f"survey_responses/{survey_name}.txt")
                            st.session_state.editable_df = pd.read_csv(f"survey_responses/{survey_name}.csv")
                            st.session_state.survey_name = survey_name
                            st.session_state.query = query
                            st.session_state.csv_editing_stage = True
                            st.rerun()
                        except FileNotFoundError:
                            st.error("Error: Your function did not create 'data.csv' or 'data.txt'.")
                    else:
                        st.error("Please enter survey requirements.")

        st.markdown("---")
        st.header(t['existing_surveys_header'])
        surveys = get_all_surveys()
        if surveys:
            df_surveys = pd.DataFrame([dict(row) for row in surveys])
            df_surveys['created_at'] = pd.to_datetime(df_surveys['created_at']).dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(df_surveys[['id', 'title', 'status', 'created_at']], use_container_width=True)

            st.subheader("Actions")
            selected_id = st.selectbox("Select Survey ID for Action", options=df_surveys['id'].tolist())
            if selected_id:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button("🚀 Deploy", key=f"deploy_{selected_id}"):
                        update_survey_status(selected_id, "Deployed")
                        st.success(f"Survey {selected_id} has been deployed.")
                        st.rerun()
                with col2:
                    survey_details = df_surveys[df_surveys['id'] == selected_id].iloc[0].to_dict()
                    if st.button("🔗 Share Form", key=f"share_{selected_id}"):
                        html_path = generate_html_form(survey_details)
                        if html_path:
                            try:
                                # Read the HTML file content
                                with open(html_path, 'r', encoding='utf-8') as f:
                                    html_content = f.read()
                                
                                # Upload to Supabase Storage
                                file_name = f"survey_{selected_id}_form.html"
                                bucket_name = "survey-forms"
                                
                                # Delete old file if exists to ensure clean upload with new content-type
                                try:
                                    supabase.storage.from_(bucket_name).remove([file_name])
                                except:
                                    pass  # File might not exist yet
                                
                                # Upload file with proper content type so browser renders HTML
                                supabase.storage.from_(bucket_name).upload(
                                    path=file_name,
                                    file=html_content.encode('utf-8'),
                                    file_options={
                                        "content-type": "text/html; charset=utf-8",
                                        "cache-control": "3600"
                                    }
                                )
                                
                                # Get public URL
                                public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
                                
                                # Display shareable link
                                st.success("✅ Shareable form generated!")
                                st.markdown(f"### 🔗 Share this link:")
                                st.code(public_url, language=None)
                                
                                # Copy button using link
                                st.link_button("📋 Open Form", public_url, use_container_width=True)
                                
                                st.info("📋 **How to use:**\n1. Copy the link above\n2. Share it with respondents via email, WhatsApp, etc.\n3. Respondents can fill the survey in any browser\n4. Responses will be saved automatically")
                                st.warning("⚠️ **Important:** Make sure the API server is running at https://vivek45537-kartavya.hf.space")
                            except Exception as e:
                                error_msg = str(e)
                                st.error(f"❌ Error uploading form: {error_msg}")
                                
                                if "403" in error_msg or "row-level security" in error_msg.lower() or "unauthorized" in error_msg.lower():
                                    st.warning("### 🔒 RLS Policy Issue Detected")
                                    st.markdown("""
                                    **Quick Fix:**
                                    1. Go to [Supabase Dashboard → Storage](https://supabase.com/dashboard)
                                    2. Click on `survey-forms` bucket
                                    3. Go to **Policies** tab
                                    4. Click **"Disable RLS"** (easiest option)
                                    
                                    OR create these policies:
                                    - **Allow public uploads**: Operation=INSERT, Target=public, Expression=`true`
                                    - **Allow public reads**: Operation=SELECT, Target=public, Expression=`true`
                                    """)
                                else:
                                    st.info("💡 **Setup Required:**\n1. Go to Supabase Dashboard → Storage\n2. Create a new bucket named 'survey-forms'\n3. Make it public\n4. Disable RLS or add upload policies\n5. Try again")
                with col3:
                    if st.button("🗑️ Delete", key=f"delete_{selected_id}"):
                        delete_survey(selected_id)
                        st.success(f"Survey {selected_id} deleted.")
                        st.rerun()
                with col4:
                    survey_details = df_surveys[df_surveys['id'] == selected_id].iloc[0]
                    with open(survey_details['json_path']) as f:
                        st.download_button(
                            label="⬇️ Download JSON",
                            data=f.read(),
                            file_name=os.path.basename(survey_details['json_path']),
                            mime='application/json',
                            key=f"json_{selected_id}"
                        )
        else:
            st.info("No surveys found.")


def render_take_survey(t):
    # Display coins at the top right (only for non-admin users)
    if st.session_state.get('role') != 'admin':
        col1, col2 = st.columns([3, 1])
        with col1:
            st.title(f"✍️ {t['nav_take_survey']}")
        with col2:
            st.markdown("###")
            st.metric("", f"🪙 {get_coins()} coins")
    else:
        st.title(f"✍️ {t['nav_take_survey']}")
    
    deployed_surveys = [s for s in get_all_surveys() if s['status'] == 'Deployed']
    if not deployed_surveys:
        st.warning(t['no_deployed_surveys_warning'])
        return

    survey_options = {f"{s['id']}: {s['title']}": s for s in deployed_surveys}
    selected_title = st.selectbox(t['select_survey_prompt'], options=survey_options.keys())
    if not selected_title:
        return

    selected_survey = survey_options[selected_title]
    st.markdown("---")
    st.subheader(t['respondent_verification_header'])
    uploaded_file = st.file_uploader(t['upload_aadhaar_prompt'], type=['jpg', 'png', 'jpeg'])

    if uploaded_file:
        image_path = os.path.join("uploads", uploaded_file.name)
        with open(image_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        with st.spinner("Processing Aadhaar card..."):
            extract_and_process(image_path)
        try:
            with open("aadhaar_output.json", "r", encoding='utf-8') as f:
                aadhaar_data = json.load(f)
            st.success("Aadhaar data extracted.")

            st.subheader(t['extracted_info_header'])
            with st.container(border=True):
                col1, col2 = st.columns(2)
                col1.text_input(t['name_label'], aadhaar_data.get('name', 'N/A'), disabled=True)
                col2.text_input(t['dob_label'], aadhaar_data.get('dob', 'N/A'), disabled=True)
                col1.text_input(t['gender_label'], aadhaar_data.get('gender', 'N/A'), disabled=True)
                st.text_area(t['address_label'], aadhaar_data.get('address', 'N/A'), disabled=True, height=100)

            respondent_id = add_respondent(selected_survey['id'], aadhaar_data.get('name'), aadhaar_data.get('dob'), aadhaar_data.get('gender'), aadhaar_data.get('aadhaar_number'), aadhaar_data.get('address'))
            render_survey_form(selected_survey, respondent_id, t)
        except Exception as e:
            st.error(f"Failed to process Aadhaar data: {e}")

def render_survey_form(survey_data, respondent_id, t):
    st.header(f"Survey: {survey_data['title']}")
    try:
        with open(survey_data['json_path'], 'r', encoding='utf-8') as f:
            questions = json.load(f)
    except FileNotFoundError:
        st.error("Survey JSON file not found.")
        return

    with st.form(f"survey_form_{respondent_id}"):
        answers = {}
        for q in questions:
            question_text, q_type, description = q.get('question', ''), q.get('type', ''), q.get('description', '')
            if any(kw in question_text.lower() for kw in ['name', 'gender', 'address']):
                continue
            st.subheader(question_text)
            if description: st.caption(description)
            if q_type == 'yes/no':
                answers[question_text] = st.radio("Select:", ["Yes", "No"], key=question_text, horizontal=True)
            elif q_type == 'rating_1_10':
                answers[question_text] = st.slider("Rating:", 1, 10, 5, key=question_text)
            else:
                answers[question_text] = st.text_area("Answer:", key=question_text)
            st.markdown("---")
        if st.form_submit_button("Submit Survey"):
            save_answers(respondent_id, answers)
            # Award random coins between 500-900
            coins_earned = random.randint(500, 900)
            add_coins(coins_earned)
            st.success(f"Survey submitted successfully! You earned 🪙 {coins_earned} coins!")
            st.info(f"Your total balance: 🪙 {get_coins()} coins")
            st.balloons()

def render_user_management(t):
    st.title(f"👥 {t['user_management_title']}")
    st.header(t['registered_users_header'])
    users = get_all_users()
    if users:
        st.dataframe(pd.DataFrame([dict(row) for row in users]), use_container_width=True)
    else:
        st.info("No users found.")

@st.cache_data(ttl=3600)  # Cache for 1 hour
def generate_visualization_config(survey_id, columns_json):
    """Generate visualization configuration using Gemini LLM and cache it."""
    try:
        columns_info = json.loads(columns_json)
        
        prompt = f"""Analyze this survey data and suggest the best visualizations. Return ONLY a valid JSON object.

IMPORTANT: You can create MULTIPLE visualizations of the same type if needed. Be smart about choosing the right charts for the data.

Example structure:
{{
  "visualizations": [
    {{"type": "pie", "column": "gender", "title": "Gender Distribution"}},
    {{"type": "pie", "column": "age_group", "title": "Age Group Distribution"}},
    {{"type": "bar", "column": "satisfaction", "title": "Satisfaction Levels"}},
    {{"type": "bar", "column": "location", "title": "Responses by Location"}},
    {{"type": "line", "x_column": "date", "y_column": "score", "title": "Score Trend"}},
    {{"type": "table", "columns": ["name", "age", "score"], "title": "Top Respondents"}}
  ]
}}

Chart Types:
- pie: Best for categorical data with 2-10 unique values (gender, yes/no, categories)
- bar: Best for categorical counts, frequencies, comparisons
- line: Best for numeric trends over time, sequences, or ordered data
- table: Best for showing detailed records with multiple columns

Guidelines:
- Create 4-8 visualizations total (mix of types)
- Use multiple pie/bar charts for different categorical columns
- Use line charts for any time-series or numeric progression data
- Include at least one table for detailed data view
- Prioritize the most insightful columns
- Skip metadata columns (id, timestamps, device_info)

Data columns:
{json.dumps(columns_info, indent=2)}

Return ONLY the JSON object, no markdown formatting, no explanation."""

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Extract JSON from response
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()
        
        viz_config = json.loads(response_text)
        return viz_config
    except Exception as e:
        st.error(f"Error generating visualization config: {e}")
        return {"visualizations": []}

def render_data_quality(t):
    st.title(f"🔍 {t['nav_data_quality']}")

    surveys = get_all_surveys()
    if not surveys:
        st.warning("No surveys have been created yet.")
        return

    survey_options = {f"{s['id']}: {s['title']}": s['id'] for s in surveys}
    selected_title = st.selectbox("Select a survey to analyze:", options=survey_options.keys(), key="data_quality_survey_select")

    if selected_title:
        survey_id = survey_options[selected_title]
        results_df = get_survey_results(survey_id)

        if results_df.empty:
            st.info("No results have been submitted for this survey yet.")
            return

        st.markdown("---")
        
        # Add cache clear button
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.subheader("📊 Data Overview")
        with col_b:
            if st.button("🔄 Regenerate Charts", help="Clear cache and generate new visualizations"):
                # Clear the specific cache for this survey
                generate_visualization_config.clear()
                st.success("Cache cleared! Regenerating...")
                st.rerun()

        # Clean data
        df_clean = results_df.copy()
        for col in df_clean.columns:
            if pd.api.types.is_numeric_dtype(df_clean[col]):
                df_clean[col].fillna(df_clean[col].median(), inplace=True)
            else:
                df_clean[col].fillna('Not Specified', inplace=True)

        # Show basic stats
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Responses", len(df_clean))
        col2.metric("Total Questions", len(df_clean.columns) - 5)  # Exclude metadata columns
        col3.metric("Completion Rate", "100%")

        st.dataframe(df_clean.head(10), use_container_width=True)

        st.markdown("---")
        st.subheader("🤖 AI-Powered Visualizations")
        
        # Prepare data summary for LLM
        columns_info = []
        for col in df_clean.columns:
            if col not in ['id', 'survey_id', 'created_at', 'start_time', 'end_time']:
                dtype = 'numeric' if pd.api.types.is_numeric_dtype(df_clean[col]) else 'categorical'
                unique_count = df_clean[col].nunique()
                columns_info.append({
                    'name': col,
                    'type': dtype,
                    'unique_values': unique_count,
                    'sample': str(df_clean[col].head(3).tolist())
                })
        
        # Auto-generate visualizations with caching
        with st.spinner("🎨 Generating smart visualizations..."):
            viz_config = generate_visualization_config(survey_id, json.dumps(columns_info))
        
        # Generate visualizations
        for idx, viz in enumerate(viz_config.get('visualizations', [])):
            viz_type = viz.get('type')
            title = viz.get('title', 'Visualization')
            
            st.markdown(f"### {idx + 1}. {title}")
            
            try:
                if viz_type == 'pie':
                    col = viz.get('column')
                    if col in df_clean.columns:
                        value_counts = df_clean[col].value_counts()
                        fig = px.pie(
                            values=value_counts.values,
                            names=value_counts.index,
                            title=title,
                            hole=0.3
                        )
                        fig.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig, use_container_width=True)
                
                elif viz_type == 'bar':
                    col = viz.get('column')
                    if col in df_clean.columns:
                        value_counts = df_clean[col].value_counts()
                        fig = px.bar(
                            x=value_counts.index,
                            y=value_counts.values,
                            title=title,
                            labels={'x': col, 'y': 'Count'}
                        )
                        fig.update_layout(showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                
                elif viz_type == 'line':
                    x_col = viz.get('x_column')
                    y_col = viz.get('y_column')
                    if x_col in df_clean.columns and y_col in df_clean.columns:
                        fig = px.line(
                            df_clean,
                            x=x_col,
                            y=y_col,
                            title=title,
                            markers=True
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                elif viz_type == 'table':
                    cols = viz.get('columns', [])
                    valid_cols = [c for c in cols if c in df_clean.columns]
                    if valid_cols:
                        st.dataframe(
                            df_clean[valid_cols].head(10),
                            use_container_width=True
                        )
                
                st.markdown("---")
            except Exception as e:
                st.warning(f"Could not generate {viz_type} chart: {e}")
        
        # Download option
        st.download_button(
            label="📥 Download Full Data",
            data=df_clean.to_csv(index=False).encode('utf-8'),
            file_name=f"survey_{survey_id}_data.csv",
            mime="text/csv"
        )
        
        # Sarvekshan AI Section
        st.markdown("---")
        st.subheader("💬 Ask Sarvekshan AI")
        st.markdown("Get insights and answers about your survey data using AI")
        
        # Initialize chat history in session state
        chat_key = f"chat_history_{survey_id}"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []
        
        # Quick action buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📊 Summarize Data", key=f"summarize_{survey_id}"):
                prompt = f"Summarize the key findings from this survey data:\n\n{df_clean.head(20).to_string()}"
                st.session_state[chat_key].append({"role": "user", "content": "Summarize the survey data"})
                with st.spinner("Analyzing..."):
                    try:
                        ai_model = genai.GenerativeModel(model_name="gemini-3-pro-preview")
                        response = ai_model.generate_content(prompt)
                        st.session_state[chat_key].append({"role": "assistant", "content": response.text})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        with col2:
            if st.button("📈 Key Insights", key=f"insights_{survey_id}"):
                prompt = f"Identify the top 3 key insights from this survey data:\n\n{df_clean.describe().to_string()}\n\nSample data:\n{df_clean.head(10).to_string()}"
                st.session_state[chat_key].append({"role": "user", "content": "What are the key insights?"})
                with st.spinner("Analyzing..."):
                    try:
                        ai_model = genai.GenerativeModel(model_name="gemini-3-pro-preview")
                        response = ai_model.generate_content(prompt)
                        st.session_state[chat_key].append({"role": "assistant", "content": response.text})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        with col3:
            if st.button("🔍 Recommendations", key=f"recommendations_{survey_id}"):
                prompt = f"Based on this survey data, provide actionable recommendations:\n\n{df_clean.head(20).to_string()}"
                st.session_state[chat_key].append({"role": "user", "content": "Give me recommendations"})
                with st.spinner("Analyzing..."):
                    try:
                        ai_model = genai.GenerativeModel(model_name="gemini-3-pro-preview")
                        response = ai_model.generate_content(prompt)
                        st.session_state[chat_key].append({"role": "assistant", "content": response.text})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # Display chat history
        if st.session_state[chat_key]:
            st.markdown("### 💭 Conversation History")
            for msg in st.session_state[chat_key]:
                if msg["role"] == "user":
                    with st.chat_message("user"):
                        st.write(msg["content"])
                else:
                    with st.chat_message("assistant", avatar="🤖"):
                        st.write(msg["content"])
        
        # Custom question input
        st.markdown("### ✍️ Ask Your Question")
        
        # Build context from data
        data_context = f"""Survey Data Summary:
- Total Responses: {len(df_clean)}
- Columns: {', '.join(df_clean.columns)}
- Sample Data:
{df_clean.head(10).to_string()}

Statistics:
{df_clean.describe().to_string()}
"""
        
        user_question = st.text_area(
            "Type your question about the survey data:",
            placeholder="e.g., What is the most common response? Are there any trends? What percentage of respondents...",
            key=f"question_input_{survey_id}",
            height=100
        )
        
        col_send, col_clear = st.columns([4, 1])
        with col_send:
            if st.button("🚀 Ask Sarvekshan AI", key=f"ask_ai_{survey_id}", use_container_width=True):
                if user_question.strip():
                    st.session_state[chat_key].append({"role": "user", "content": user_question})
                    
                    # Build conversation history for context
                    conversation_context = "\n\n".join([
                        f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                        for msg in st.session_state[chat_key][-4:]  # Last 2 exchanges
                    ])
                    
                    full_prompt = f"""{data_context}

Previous conversation:
{conversation_context}

Answer the user's question based on the survey data above. Be specific, use data to support your answers, and provide actionable insights."""
                    
                    with st.spinner("🤖 Sarvekshan AI is thinking..."):
                        try:
                            ai_model = genai.GenerativeModel(model_name="gemini-3-pro-preview")
                            response = ai_model.generate_content(full_prompt)
                            st.session_state[chat_key].append({"role": "assistant", "content": response.text})
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                else:
                    st.warning("Please enter a question")
        
        with col_clear:
            if st.button("🗑️ Clear", key=f"clear_chat_{survey_id}", use_container_width=True):
                st.session_state[chat_key] = []
                st.rerun()

def render_settings(t):
    st.title(f"⚙️ {t['nav_settings']}")
    st.info("This section is under development.")

def logout():
    """Clears the session state to log the user out."""
    keys_to_clear = [
        'logged_in', 'role', 'username', 'language',
        'csv_editing_stage', 'editable_df', 'survey_name', 'query',
        'question_review_stage', 'json_path', 'description',
        'script_path', 'script_data', 'survey_id'
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def main_app():
    """Main function to run the Streamlit app."""
    st.set_page_config(page_title="Survey Admin Portal", layout="wide")

    init_config()
    init_db()

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        render_login_page()
    else:
        t = TRANSLATIONS.get(st.session_state.language, TRANSLATIONS.get('en', {}))

        with st.sidebar:
            st.title(t.get('app_title', 'Survey Portal'))
            st.write(t.get('app_subtitle', 'Management'))
            st.markdown("---")

            if st.session_state.role == 'admin':
                page_options = ["nav_dashboard", "nav_survey_management", "nav_user_management", "nav_take_survey", "nav_data_quality", "nav_store", "nav_settings"]
                page = st.radio("Navigation", page_options, format_func=lambda p: t.get(p, p) if p != "nav_store" else "🏪 Store", label_visibility="collapsed")
            else: # Enumerator
                page_options = ["nav_user_dashboard", "nav_take_survey", "nav_store"]
                page = st.radio("Navigation", page_options, format_func=lambda p: t.get(p, p) if p != "nav_store" else "🏪 Store", label_visibility="collapsed")

            st.markdown("---")
            if st.button(t.get('logout_button', 'Logout')):
                logout()

        if page == "nav_dashboard": render_dashboard(t)
        elif page == "nav_user_dashboard": render_user_dashboard(t)
        elif page == "nav_survey_management": render_survey_management(t)
        elif page == "nav_take_survey": render_take_survey(t)
        elif page == "nav_user_management": render_user_management(t)
        elif page == "nav_data_quality": render_data_quality(t)
        elif page == "nav_store": render_store(t)
        elif page == "nav_settings": render_settings(t)

if __name__ == "__main__":
    main_app()
