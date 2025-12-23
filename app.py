import streamlit as st
import pandas as pd
import json
import os
import sqlite3
import requests
import time
from datetime import datetime
import joblib
import hashlib
import shutil
import webbrowser
from content import HTML_TEMPLATE # Import the HTML template
import plotly.express as px
import google.generativeai as genai
import ds_r1 , adhr 



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

# Ollama configuration for offline mode
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma2"

# --- Import your custom functions ---
# Ensure ds_r1.py and adhr.py are in the same directory as this script.
try:
    from ds_r1 import generate_survey_design
    from adhr import extract_and_process
except ImportError:
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
        st.error(f"`{LANG_FILE}` not found. Please create it with your translations.")
        return {} # Return empty dict to prevent crash
    except json.JSONDecodeError:
        st.error(f"Error decoding `{LANG_FILE}`. Please ensure it is a valid JSON file.")
        return {}

TRANSLATIONS = load_translations()

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
            st.error(f"Ollama API error: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to Ollama. Please ensure Ollama is running with 'ollama serve' and the model 'gemma2' is installed.")
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

def init_config():
    """Creates a default config file if it doesn't exist."""
    # Initialize LLM mode if not already set
    if 'llm_mode' not in st.session_state:
        st.session_state.llm_mode = 'online'
    
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
                },
                {
                    "username": "developer",
                    "password_hash": hash_password("45537")
                }
            ]
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=4)

def load_config():
    """Loads the configuration from the JSON file."""
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the database. Creates tables if they don't exist and
    updates existing tables with new columns to prevent errors.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # --- Surveys Table ---
    cursor.execute('''CREATE TABLE IF NOT EXISTS surveys (id INTEGER PRIMARY KEY, title TEXT, description TEXT, status TEXT DEFAULT 'Draft', json_path TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # --- Users Table (Schema updated to use 'username' instead of 'aadhaar_number') ---
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'Enumerator', language TEXT DEFAULT 'en', contact TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # --- Respondents Table (with new metadata columns) ---
    cursor.execute('''CREATE TABLE IF NOT EXISTS respondents (
        id INTEGER PRIMARY KEY, survey_id INTEGER, name TEXT, dob TEXT, gender TEXT, 
        aadhaar_number TEXT UNIQUE, address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        start_time TEXT, end_time TEXT, device_info TEXT, geo_latitude TEXT, geo_longitude TEXT,
        ip_address TEXT, ip_city TEXT, ip_country TEXT,
        FOREIGN KEY (survey_id) REFERENCES surveys (id)
    )''')
    
    # --- Answers Table ---
    cursor.execute('''CREATE TABLE IF NOT EXISTS answers (id INTEGER PRIMARY KEY, respondent_id INTEGER, question TEXT, answer TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (respondent_id) REFERENCES respondents (id))''')
    
    conn.commit()
    conn.close()

# --- User and Survey CRUD Functions ---
def add_user(name, username, password, language, contact):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (name, username, password, language, contact) VALUES (?, ?, ?, ?, ?)",
            (name, username, hash_password(password), language, contact)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # User already exists
    finally:
        conn.close()

def get_user(username):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user

def add_survey(title, description, status, json_path):
    conn = get_db_connection()
    conn.execute("INSERT INTO surveys (title, description, status, json_path) VALUES (?, ?, ?, ?)", (title, description, status, json_path))
    conn.commit()
    conn.close()

def get_all_surveys():
    conn = get_db_connection()
    surveys = conn.execute("SELECT * FROM surveys ORDER BY created_at DESC").fetchall()
    conn.close()
    return surveys
    
def update_survey_status(survey_id, status):
    conn = get_db_connection()
    conn.execute("UPDATE surveys SET status = ? WHERE id = ?", (status, survey_id))
    conn.commit()
    conn.close()

def delete_survey(survey_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM surveys WHERE id = ?", (survey_id,))
    conn.commit()
    conn.close()
    
def get_all_users():
    conn = get_db_connection()
    users = conn.execute("SELECT id, name, username, role, language, contact FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return users

def add_respondent(survey_id, name, dob, gender, aadhaar, address):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO respondents (survey_id, name, dob, gender, aadhaar_number, address) VALUES (?, ?, ?, ?, ?, ?)",(survey_id, name, dob, gender, aadhaar, address))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return conn.execute("SELECT id FROM respondents WHERE aadhaar_number = ?", (aadhaar,)).fetchone()['id']
    finally:
        conn.close()

def save_answers(respondent_id, answers_dict):
    conn = get_db_connection()
    for question, answer in answers_dict.items():
        conn.execute("INSERT INTO answers (respondent_id, question, answer) VALUES (?, ?, ?)",(respondent_id, question, str(answer)))
    conn.commit()
    conn.close()

def get_survey_results(survey_id):
    """
    Fetches all results from the database (from both app and web forms)
    and returns a single, combined DataFrame.
    """
    conn = get_db_connection()
    try:
        # 1. Get all respondents for this survey
        respondents_df = pd.read_sql_query(f"SELECT * FROM respondents WHERE survey_id = {survey_id}", conn)
        if respondents_df.empty:
            return pd.DataFrame()

        # 2. Get all answers for these respondents
        respondent_ids = tuple(respondents_df['id'].tolist())
        
        # --- FIX: Correctly format the tuple for the SQL IN clause ---
        if len(respondent_ids) == 1:
            # For a single ID, create a string like '(1)' instead of '(1,)'
            respondent_ids_sql = f"({respondent_ids[0]})"
        else:
            respondent_ids_sql = str(respondent_ids)

        answers_df = pd.read_sql_query(f"SELECT * FROM answers WHERE respondent_id IN {respondent_ids_sql}", conn)
        
        # 3. Pivot the answers from long to wide format
        if not answers_df.empty:
            pivoted_answers_df = answers_df.pivot(index='respondent_id', columns='question', values='answer').reset_index()
            # 4. Merge respondent data with their answers
            results_df = pd.merge(respondents_df, pivoted_answers_df, left_on='id', right_on='respondent_id', how='left')
            return results_df
        else:
            return respondents_df # Return just respondent data if no answers are logged yet
    finally:
        conn.close()


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
        return None
    
    survey_questions = []
    progress_bar = st.progress(0, text="Initializing LLM...")
    for i, header in enumerate(df.columns):
        progress_text = f"Generating question for '{header}'... ({i+1}/{len(df.columns)})"
        st.toast(progress_text)
        progress_bar.progress((i + 1) / len(df.columns), text=progress_text)
        
        try:
            prompt = f"""Given a survey about '{survey_description}', generate a JSON object for a single survey question based on the data field '{header}'. The JSON object must have ONLY three keys: "question", "description", and "type" (choose from 'text', 'yes/no', or 'rating_1_10')."""
            
            response_text = generate_with_llm(prompt)
            if not response_text:
                raise Exception("LLM returned empty response")
            
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
                survey_questions.append({
                    "question": header.replace('_', ' ').title(),
                    "description": "Please provide your input for this question.",
                    "type": "text"
                })

        except Exception as e:
            st.error(f"Failed to connect to Google Gemini API. Please check your API key.")
            st.error(f"Error details: {e}")
            return None 

        except (json.JSONDecodeError, Exception) as e:
            st.warning(f"Could not generate a valid question for '{header}': {e}. Using a default question.")
            survey_questions.append({
                "question": header.replace('_', ' ').title(),
                "description": "Please provide your input for this question.",
                "type": "text"
            })

    progress_bar.empty()
    json_path = os.path.join("survey_jsons", f"{survey_name}.json")
    with open(json_path, "w", encoding='utf-8') as f:
        json.dump(survey_questions, f, indent=2, ensure_ascii=False)
    return json_path, survey_description


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

    # Use the imported template
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
    # Use English for the login page itself for consistency
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
                        # Set developer flag
                        st.session_state.is_developer = (admin_user == "developer")
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
                    st.session_state.is_developer = False
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
    
    # Add custom CSS for animated toggle
    st.markdown("""
    <style>
    .mode-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        margin: 20px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .mode-title {
        color: white;
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 10px;
        text-align: center;
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
            # Pass the mode to ds_r1
            os.environ['LLM_MODE'] = 'online'
            st.success("✅ Switched to Online Mode (Gemini API)")
            time.sleep(0.5)
            st.rerun()
    
    with col_mode2:
        if st.button("🔒 Offline & Secure (Gemma 3)", 
                    type="primary" if current_mode == 'offline' else "secondary",
                    use_container_width=True):
            st.session_state.llm_mode = 'offline'
            # Pass the mode to ds_r1
            os.environ['LLM_MODE'] = 'offline'
            st.success("✅ Switched to Offline & Secure Mode (Ollama Gemma 3)")
            time.sleep(0.5)
            st.rerun()
    
    # Display current mode status with animation
    mode_emoji = "🌐" if current_mode == 'online' else "🔒"
    mode_text = "Online (Gemini API)" if current_mode == 'online' else "Offline & Secure (Local Gemma 3)"
    st.markdown(f'<div class="mode-status">{mode_emoji} Current Mode: {mode_text}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    conn = get_db_connection()
    total_surveys = conn.execute("SELECT COUNT(*) FROM surveys").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'Enumerator'").fetchone()[0]
    completed_respondents = conn.execute("SELECT COUNT(*) FROM respondents").fetchone()[0]
    conn.close()
    col1, col2, col3 = st.columns(3)
    col1.metric(t['metric_total_surveys'], total_surveys)
    col2.metric(t['metric_registered_enumerators'], total_users)
    col3.metric(t['metric_surveys_completed'], completed_respondents)

def render_user_dashboard(t):
    st.title(f"👋 {t['user_dashboard_welcome']}, {st.session_state.username}!")
    st.markdown("---")
    
    deployed_surveys = [s for s in get_all_surveys() if s['status'] == 'Deployed']
    st.metric(t['metric_available_surveys'], len(deployed_surveys))
    
    st.markdown("---")
    st.subheader("Quick Actions")
    st.info("Navigate to 'Take a Survey' from the sidebar to begin.")

def render_survey_management(t):
    st.title(f"📝 {t['nav_survey_management']}")

    # --- NEW: Developer Mode UI ---
    if st.session_state.get("is_developer", False):
        st.info("🚀 Developer Mode Activated")
        dev_mode = st.radio("Developer Mode:", ("Generate New (LLM)", "Use Dev Files (Skip LLM)"), horizontal=True)
    else:
        dev_mode = "Generate New (LLM)"


    # --- CSV Editing Stage ---
    if 'csv_editing_stage' in st.session_state and st.session_state.csv_editing_stage:
        st.subheader("Step 2: Review and Edit Survey Columns")
        st.info("Here you can add, rename, or delete columns before generating the final questions. To delete, select a column and press the 'Delete' key.")

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
                result = create_survey_json_iteratively(survey_name)
            if result:
                json_path, description = result
                with st.spinner("Finalizing and saving survey..."):
                    add_survey(st.session_state.query.split('.')[0], description, 'Draft', json_path)
                st.success(f"🎉 Survey created!")
                for key in ['csv_editing_stage', 'editable_df', 'survey_name', 'query']:
                    del st.session_state[key]
                st.rerun()
    
    # --- Original Survey Creation Form ---
    else:
        with st.expander(f"➕ {t['create_new_survey_expander']}", expanded=True):
            with st.form("survey_creation_form"):
                query = st.text_area(t['generate_survey_prompt'], height=150, disabled=(dev_mode == "Use Dev Files (Skip LLM)"))
                
                if st.form_submit_button(t['generate_survey_button']):
                    # --- Developer Skip Logic ---
                    if dev_mode == "Use Dev Files (Skip LLM)":
                        try:
                            with open("assets/devquery.txt", "r") as f:
                                dev_query = f.read().strip()
                            
                            survey_name = create_unique_survey_name(dev_query)
                            
                            # Copy dev files to new unique names
                            shutil.copy("survey_responses/dev.csv", f"survey_responses/{survey_name}.csv")
                            shutil.copy("survey_responses/dev.txt", f"survey_responses/{survey_name}.txt")
                            shutil.copy("survey_jsons/dev.json", f"survey_jsons/{survey_name}.json")

                            with open(f"survey_responses/{survey_name}.txt", "r") as f:
                                description = f.read().strip()

                            add_survey(dev_query, description, 'Draft', f"survey_jsons/{survey_name}.json")
                            st.success("🎉 Dev survey created instantly!")
                            st.rerun()

                        except FileNotFoundError as e:
                            st.error(f"Developer file not found: {e}. Please create dev.csv, dev.txt, assets/devquery.txt, and dev.json.")

                    # --- Standard Generation Logic ---
                    elif query.strip():
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
                        webbrowser.open(f"file://{os.path.abspath(html_path)}")
                        st.success("Shareable form generated and opened in a new browser tab.")
                        st.info("Please ensure the `api.py` server is running in a separate terminal for submissions to work.")

            with col3:
                if st.button("🗑️ Delete", key=f"delete_{selected_id}"):
                    delete_survey(selected_id)
                    st.success(f"Survey {selected_id} deleted.")
                    st.rerun()
            
            with col4:
                survey_details = df_surveys[df_surveys['id'] == selected_id].iloc[0]
                if st.button("⬇️ Download JSON", key=f"json_{selected_id}"):
                    with open(survey_details['json_path']) as f:
                        st.download_button(
                            label="Download Survey JSON",
                            data=f.read(),
                            file_name=os.path.basename(survey_details['json_path']),
                            mime='application/json'
                        )
    else:
        st.info("No surveys found.")

def render_take_survey(t):
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
            st.success("Survey submitted successfully!")
            st.balloons()
            
def render_user_management(t):
    st.title(f"👥 {t['user_management_title']}")
    st.header(t['registered_users_header'])
    users = get_all_users()
    if users:
        st.dataframe(pd.DataFrame([dict(row) for row in users]), use_container_width=True)
    else:
        st.info("No users found.")
        
def render_data_quality(t):
    st.title(f"🔍 {t['nav_data_quality']}")
    
    surveys = get_all_surveys()
    if not surveys:
        st.warning("No surveys have been created yet.")
        return

    survey_options = {f"{s['id']}: {s['title']}": s['id'] for s in surveys}
    selected_title = st.selectbox("Select a survey to analyze:", options=survey_options.keys())
    
    if selected_title:
        survey_id = survey_options[selected_title]
        results_df = get_survey_results(survey_id)

        if results_df.empty:
            st.info("No results have been submitted for this survey yet.")
            return

        st.markdown("---")
        st.subheader("Data Overview & Preprocessing")

        # Basic preprocessing
        df_clean = results_df.copy()
        for col in df_clean.columns:
            if pd.api.types.is_numeric_dtype(df_clean[col]):
                df_clean[col].fillna(df_clean[col].median(), inplace=True)
            else:
                df_clean[col].fillna('Not Specified', inplace=True)
        
        st.dataframe(df_clean)

        st.markdown("---")
        st.subheader("AI-Powered Summary")
        if st.button("Generate Summary"):
            with st.spinner("Generating insights with Gemini..."):
                try:
                    # --- FIX: Two-step summary generation ---
                    # 1. Identify key columns
                    with st.spinner("Step 1/2: Identifying key columns for summary..."):
                        all_columns = ", ".join(df_clean.columns)
                        prompt1 = f"From this list of survey columns, identify the 4 most insightful for a summary. Respond with only a comma-separated list of column names. Columns: {all_columns}"
                        key_columns_str = generate_with_llm(prompt1)
                        if not key_columns_str:
                            raise Exception("Failed to identify key columns")
                        key_columns = [col.strip() for col in key_columns_str.split(',') if col.strip() in df_clean.columns]

                    # 2. Generate summary from key columns
                    with st.spinner("Step 2/2: Generating summary from key data..."):
                        if not key_columns: # Fallback if first step fails
                             key_columns = df_clean.columns[:5].tolist()
                        
                        data_sample = df_clean[key_columns].head(20).to_string()
                        prompt2 = f"Analyze the following key data from a survey and provide a brief, high-level summary of the findings:\n\n{data_sample}"
                        summary = generate_with_llm(prompt2)
                        if summary:
                            st.success(summary)
                        else:
                            st.error("Failed to generate summary")

                except Exception as e:
                    st.error(f"Failed to generate summary: {e}")

        st.markdown("---")
        st.subheader("Visual Analytics")
        
        for col in df_clean.columns:
            # Skip metadata and high-cardinality columns for cleaner charts
            if col in ['id', 'respondent_id', 'survey_id', 'name', 'address', 'start_time', 'end_time', 'device_info'] or df_clean[col].nunique() > 50:
                continue

            with st.container(border=True):
                st.write(f"**Analysis for: `{col}`**")
                if pd.api.types.is_numeric_dtype(df_clean[col]) and df_clean[col].nunique() > 10:
                    fig = px.histogram(df_clean, x=col, title=f"Distribution of {col}")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    fig = px.bar(df_clean[col].value_counts(), title=f"Count of {col}")
                    st.plotly_chart(fig, use_container_width=True)

def render_settings(t):
    st.title(f"⚙️ {t['nav_settings']}")
    st.info("This section is under development.")

def logout():
    """Clears the session state to log the user out."""
    for key in ['logged_in', 'role', 'username', 'language', 'csv_editing_stage', 'editable_df', 'survey_name', 'query', 'is_developer']:
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
                page_options = ["nav_dashboard", "nav_survey_management", "nav_user_management", "nav_take_survey", "nav_data_quality", "nav_settings"]
                page = st.radio("Navigation", page_options, format_func=lambda p: t.get(p, p), label_visibility="collapsed")
            else: # Enumerator
                page_options = ["nav_user_dashboard", "nav_take_survey"]
                page = st.radio("Navigation", page_options, format_func=lambda p: t.get(p, p), label_visibility="collapsed")

            st.markdown("---")
            if st.button(t.get('logout_button', 'Logout')):
                logout()

        if page == "nav_dashboard": render_dashboard(t)
        elif page == "nav_user_dashboard": render_user_dashboard(t)
        elif page == "nav_survey_management": render_survey_management(t)
        elif page == "nav_take_survey": render_take_survey(t)
        elif page == "nav_user_management": render_user_management(t)
        elif page == "nav_data_quality": render_data_quality(t)
        elif page == "nav_settings": render_settings(t)

if __name__ == "__main__":
    main_app()




