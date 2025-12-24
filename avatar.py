# # --- FIX: Disable problematic file watcher before Streamlit import ---
# import os
# os.environ['STREAMLIT_SERVER_FILE_WATCHER_TYPE'] = 'none'

# import streamlit as st
# import numpy as np
# from gtts import gTTS
# import json
# import sqlite3
# import requests
# import io
# import time
# import uuid
# import wave
# import sounddevice as sd
# import soundfile as sf
# import hashlib
# import shutil
# from pathlib import Path

# # --- PROJECT SETUP & CONFIG ---
# # Create necessary directories
# os.makedirs("survey_jsons", exist_ok=True)
# os.makedirs("temp_audio", exist_ok=True)
# os.makedirs("survey_scripts", exist_ok=True)
# os.makedirs("tts_cache", exist_ok=True) # Directory for cached TTS audio
# DB_NAME = "survey_portal.db"

# # --- AVATAR FILES ---
# # User should place their avatar files in the root directory
# AVATAR_ANIMATED_PATH = "avatar.gif"
# AVATAR_STATIC_PATH = "avatar_static.png"

# # --- DATABASE HELPER ---
# def get_db_connection():
#     """Establishes a connection to the SQLite database."""
#     conn = sqlite3.connect(DB_NAME)
#     conn.row_factory = sqlite3.Row
#     return conn

# def get_all_surveys():
#     """Fetches all 'Deployed' surveys from the database."""
#     conn = get_db_connection()
#     surveys = conn.execute("SELECT * FROM surveys WHERE status = 'Deployed' ORDER BY created_at DESC").fetchall()
#     conn.close()
#     return surveys

# # --- CORE FUNCTIONS ---

# @st.cache_resource
# def load_whisper_model():
#     """Loads the Whisper model and caches it in Streamlit's resource cache."""
#     import whisper
#     st.info("Loading speech recognition model (this happens once)...")
#     model = whisper.load_model("base")
#     st.success("Speech recognition model loaded.")
#     return model

# def text_to_speech(text, lang='en', slow=False):
#     """
#     Converts text to speech. Checks for a cached version first.
#     If not found, generates audio using gTTS, saves it to the cache,
#     and then returns the audio data.
#     """
#     cache_dir = "tts_cache"
#     # Create a unique, filesystem-safe filename based on the hash of the text and language
#     file_hash = hashlib.md5((text + lang + str(slow)).encode('utf-8')).hexdigest()
#     cached_file_path = os.path.join(cache_dir, f"{file_hash}.mp3")

#     if os.path.exists(cached_file_path):
#         with open(cached_file_path, "rb") as f:
#             return f.read()
#     else:
#         try:
#             tts = gTTS(text=text, lang=lang, slow=slow)
#             fp = io.BytesIO()
#             tts.write_to_fp(fp)
#             fp.seek(0)
#             audio_data = fp.read()
#             with open(cached_file_path, "wb") as f:
#                 f.write(audio_data)
#             return audio_data
#         except Exception as e:
#             st.error(f"Failed to generate TTS audio for '{text}': {e}")
#             return None


# def generate_survey_script(questions_json, script_path, ollama_api_url="http://localhost:11434/api/generate"):
#     """
#     Generates a full conversational script from survey questions by processing one question at a time
#     to prevent timeouts, and saves it to a file.
#     """
#     script = []
#     progress_bar = st.progress(0, text="Generating conversational script...")

#     for i, question_data in enumerate(questions_json):
#         progress_text = f"Generating script for question {i+1}/{len(questions_json)}..."
#         progress_bar.progress((i + 1) / len(questions_json), text=progress_text)

#         try:
#             prompt = f"""
#             You are creating a single step for a conversational survey. Based on the following question details, create a JSON object with three keys:
#             1. "say": A friendly, conversational way to ask this question.
#             2. "explain": A slightly more detailed explanation of the question if the user asks for one.
#             3. "question_key": The original question text to use as a key for saving the answer.
#             The final output must be a single, valid JSON object for this one question.
#             Question Details: {json.dumps(question_data)}
#             """
#             payload = {"model": "gemma3n", "prompt": prompt, "stream": False, "format": "json"}
#             response = requests.post(ollama_api_url, json=payload, timeout=60)
#             response.raise_for_status()
#             script_part = json.loads(response.json().get("response", "{}"))
#             if all(k in script_part for k in ["say", "explain", "question_key"]):
#                 script.append(script_part)
#             else:
#                 raise ValueError("LLM response did not contain required keys.")
#         except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError) as e:
#             st.warning(f"Failed to generate script for a question ({e}). Using default format.")
#             script.append({
#                 "say": question_data['question'],
#                 "explain": question_data.get('description', 'No further details.'),
#                 "question_key": question_data['question']
#             })

#     progress_bar.empty()
#     with open(script_path, "w", encoding="utf-8") as f:
#         json.dump(script, f, indent=4)
#     return script

# def extract_answer_from_text(question, text, ollama_api_url="http://localhost:11434/api/generate"):
#     """Uses an LLM to extract a concise answer from transcribed text."""
#     try:
#         prompt = f"""
#         Given the survey question and the user's transcribed response, extract the single, most direct answer.
#         - For ratings, extract the number.
#         - For yes/no questions, extract "Yes" or "No".
#         - For open-ended questions, provide a concise summary of the response.
#         Respond with ONLY the extracted answer.
#         Question: "{question}"
#         User's Response: "{text}"
#         Extracted Answer:
#         """
#         payload = {"model": "gemma3n", "prompt": prompt, "stream": False}
#         response = requests.post(ollama_api_url, json=payload, timeout=60)
#         response.raise_for_status()
#         return response.json().get("response", text).strip()
#     except Exception as e:
#         st.warning(f"LLM extraction failed: {e}. Using raw text.")
#         return text

# def record_audio(duration=5, sample_rate=44100):
#     """Records audio using sounddevice and returns the file path."""
#     audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
#     sd.wait()
#     session_audio_dir = os.path.join("temp_audio", st.session_state.session_id)
#     os.makedirs(session_audio_dir, exist_ok=True)
#     file_path = os.path.join(session_audio_dir, f"answer_{st.session_state.current_step}.wav")
#     sf.write(file_path, audio_data, sample_rate)
#     return file_path

# # --- STREAMLIT UI ---

# def initialize_session_state():
#     """Initializes all necessary session state variables."""
#     if 'page' not in st.session_state:
#         st.session_state.page = "setup"
#     if 'survey_paused' not in st.session_state:
#         st.session_state.survey_paused = False
#     if 'avatar_state' not in st.session_state:
#         st.session_state.avatar_state = 'static' # 'static' or 'playing'
#     if 'survey_flow_state' not in st.session_state:
#         # 'asking', 'countdown', 'recording', 'processing_answer'
#         st.session_state.survey_flow_state = 'asking'

# def render_setup_page():
#     """Renders the initial setup form."""
#     st.header("Step 1: Setup Your Survey Session")
#     # Check for avatar files
#     if not Path(AVATAR_ANIMATED_PATH).is_file() or not Path(AVATAR_STATIC_PATH).is_file():
#         st.error(
#             f"Avatar files not found! Please make sure '{AVATAR_ANIMATED_PATH}' and "
#             f"'{AVATAR_STATIC_PATH}' are in the same directory as the script."
#         )
#         st.stop()

#     surveys = get_all_surveys()
#     if not surveys:
#         st.warning("No deployed surveys found. Please create and deploy a survey in the admin portal.")
#         return

#     survey_options = {f"{s['id']}: {s['title']}": s for s in surveys}
#     with st.form("setup_form"):
#         name = st.text_input("Your Name")
#         language = st.selectbox("Select Language", options=['en', 'hi'], format_func=lambda x: "English" if x == 'en' else "हिंदी")
#         selected_survey_title = st.selectbox("Select a Survey", options=survey_options.keys())
#         submitted = st.form_submit_button("Start Survey")

#         if submitted and name and selected_survey_title:
#             st.session_state.name = name
#             st.session_state.language = language
#             st.session_state.selected_survey = survey_options[selected_survey_title]
#             st.session_state.session_id = str(uuid.uuid4())
#             survey_id = st.session_state.selected_survey['id']
#             script_path = os.path.join("survey_scripts", f"script_{survey_id}.json")

#             script = None
#             if os.path.exists(script_path):
#                 with st.spinner("Loading existing survey script..."):
#                     with open(script_path, 'r', encoding='utf-8') as f:
#                         script = json.load(f)
#             else:
#                 try:
#                     with open(st.session_state.selected_survey['json_path'], 'r', encoding='utf-8') as f:
#                         questions_json = json.load(f)
#                     script = generate_survey_script(questions_json, script_path)
#                 except Exception as e:
#                     st.error(f"Failed to load or process survey: {e}")

#             if script:
#                 st.session_state.script = script
#                 st.session_state.current_step = 0
#                 st.session_state.recorded_answers = []
#                 st.session_state.page = "survey"
#                 initialize_session_state() # Re-initialize for the new survey

#                 with st.spinner("Preparing survey audio..."):
#                     audio_paths = {}
#                     session_audio_dir = os.path.join("temp_audio", st.session_state.session_id)
#                     os.makedirs(session_audio_dir, exist_ok=True)
#                     for i, step in enumerate(script):
#                         say_audio = text_to_speech(step['say'], language)
#                         explain_audio = text_to_speech(step['explain'], language)
#                         say_path = os.path.join(session_audio_dir, f"say_{i}.mp3")
#                         explain_path = os.path.join(session_audio_dir, f"explain_{i}.mp3")
#                         if say_audio:
#                             with open(say_path, "wb") as f: f.write(say_audio)
#                         if explain_audio:
#                             with open(explain_path, "wb") as f: f.write(explain_audio)
#                         audio_paths[i] = {"say": say_path, "explain": explain_path}
#                     st.session_state.audio_paths = audio_paths
#                 st.rerun()
#             else:
#                 st.error("Could not load or generate the survey script.")
#         elif submitted:
#             st.error("Please provide your name and select a survey.")

# def render_survey_page():
#     """Renders the automated, avatar-driven survey interface."""
#     step_index = st.session_state.current_step
#     script = st.session_state.script

#     if step_index >= len(script):
#         st.session_state.page = "processing"
#         st.rerun()
#         return

#     current_step_data = script[step_index]
#     question_to_say = current_step_data['say']

#     # --- Main Display ---
#     st.header(f"Question {step_index + 1}/{len(script)}")
    
#     # Avatar display
#     avatar_placeholder = st.empty()
#     if st.session_state.avatar_state == 'playing':
#         avatar_placeholder.image(AVATAR_ANIMATED_PATH)
#     else:
#         avatar_placeholder.image(AVATAR_STATIC_PATH)

#     st.title(question_to_say)
#     st.markdown("---")

#     # --- Controls ---
#     col1, col2 = st.columns(2)
#     with col1:
#         if st.session_state.survey_paused:
#             if st.button("▶️ Resume Survey", use_container_width=True):
#                 st.session_state.survey_paused = False
#                 st.rerun()
#         else:
#             if st.button("⏸️ Pause Survey", use_container_width=True):
#                 st.session_state.survey_paused = True
#                 st.rerun()
#     with col2:
#         if st.button("💡 Explain Question", use_container_width=True):
#             st.audio(st.session_state.audio_paths[step_index]['explain'], autoplay=True)
#             st.info(current_step_data['explain'])
    
#     # --- Automation Flow ---
#     if st.session_state.survey_paused:
#         st.warning("Survey is paused. Press Resume to continue.")
#         st.stop()

#     flow_state = st.session_state.survey_flow_state
    
#     if flow_state == 'asking':
#         st.session_state.avatar_state = 'playing'
#         st.audio(st.session_state.audio_paths[step_index]['say'], autoplay=True)
#         st.session_state.survey_flow_state = 'countdown'
#         # Give audio time to play before rerunning
#         # This is an approximation. A more robust solution might use JS callbacks.
#         time.sleep(3) # Adjust based on average question length
#         st.rerun()

#     elif flow_state == 'countdown':
#         st.session_state.avatar_state = 'static'
#         st.subheader("Get ready to answer...")
#         countdown_placeholder = st.empty()
#         for i in range(5, 0, -1):
#             countdown_placeholder.metric("Recording in...", f"{i} seconds")
#             time.sleep(1)
#         countdown_placeholder.empty()
#         st.session_state.survey_flow_state = 'recording'
#         st.rerun()

#     elif flow_state == 'recording':
#         st.session_state.avatar_state = 'static'
#         st.info("🎙️ Recording your answer now...")
#         audio_path = record_audio(duration=5) # Fixed 5-second recording
#         st.session_state.recorded_answers.append(audio_path)
#         st.success(f"Answer for question {step_index + 1} recorded!")
#         st.session_state.current_step += 1
#         st.session_state.survey_flow_state = 'asking' # Reset for next question
#         time.sleep(1)
#         st.rerun()


# def render_processing_page():
#     """Processes all recorded answers in a batch after the survey is complete."""
#     model = load_whisper_model()
#     st.header("Survey Complete!")
#     st.info("Thank you for your responses. Now processing your answers, please wait.")
#     final_answers = {}
#     progress_bar = st.progress(0, text="Starting processing...")

#     for i, audio_path in enumerate(st.session_state.recorded_answers):
#         question_key = st.session_state.script[i]['question_key']
#         progress_text = f"Processing answer {i+1}/{len(st.session_state.recorded_answers)}..."
#         progress_bar.progress((i + 1) / len(st.session_state.recorded_answers), text=progress_text)
#         try:
#             with st.spinner(f"Transcribing answer {i+1}..."):
#                 result = model.transcribe(audio_path, fp16=False)
#                 transcribed_text = result["text"].strip()
#             with st.spinner(f"Extracting key info from answer {i+1}..."):
#                 extracted_answer = extract_answer_from_text(question_key, transcribed_text)
#             final_answers[question_key] = extracted_answer
#         except Exception as e:
#             st.error(f"Could not process answer {i+1}: {e}")
#             final_answers[question_key] = "ERROR - COULD NOT PROCESS AUDIO"

#     progress_bar.empty()
#     st.success("✅ All answers processed!")
#     st.subheader("Final Results:")
#     st.json(final_answers)

#     if st.button("Submit Results to Server"):
#         with st.spinner("Submitting..."):
#             try:
#                 api_url = f"http://127.0.0.1:8000/submit/{st.session_state.selected_survey['id']}"
#                 response = requests.post(api_url, json=final_answers)
#                 response.raise_for_status()
#                 st.success("Results submitted successfully via API!")
#             except Exception as e:
#                 st.error(f"Failed to submit results via API: {e}")

#     if st.button("Start New Survey"):
#         session_audio_dir = os.path.join("temp_audio", st.session_state.session_id)
#         shutil.rmtree(session_audio_dir, ignore_errors=True)
#         for key in list(st.session_state.keys()):
#             if key != 'webrtc_contexts':
#                 del st.session_state[key]
#         st.rerun()

# # --- Main App Logic ---
# def main():
#     """Main function to run the Streamlit app."""
#     st.set_page_config(page_title="Voice Survey Avatar", layout="centered")
#     st.title("🎙️ Voice Survey Avatar")
#     initialize_session_state()

#     if st.session_state.page == "setup":
#         render_setup_page()
#     elif st.session_state.page == "survey":
#         render_survey_page()
#     elif st.session_state.page == "processing":
#         render_processing_page()

# if __name__ == "__main__":
#     main()
# --- FIX: Disable problematic file watcher before Streamlit import ---
import os
os.environ['STREAMLIT_SERVER_FILE_WATCHER_TYPE'] = 'none'

import streamlit as st
import numpy as np
from gtts import gTTS
import json
import sqlite3
import requests
import io
import time
import uuid
import wave
import sounddevice as sd
import soundfile as sf
import hashlib
import shutil
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Google Generative AI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_API_KEY_HERE":
    st.error("Please set GOOGLE_API_KEY in your .env file")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(model_name="gemini-3-flash-preview")

# --- PROJECT SETUP & CONFIG ---
# Create necessary directories
os.makedirs("survey_jsons", exist_ok=True)
os.makedirs("temp_audio", exist_ok=True)
os.makedirs("survey_scripts", exist_ok=True)
os.makedirs("tts_cache", exist_ok=True) # Directory for cached TTS audio
DB_NAME = "survey_portal.db"

# --- AVATAR FILES ---
# User should place their avatar files in the root directory
AVATAR_ANIMATED_PATH = "assets/avatar.gif"
AVATAR_STATIC_PATH = "assets/avatar_static.png"

# --- DATABASE HELPER ---
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_surveys():
    """Fetches all 'Deployed' surveys from the database."""
    conn = get_db_connection()
    surveys = conn.execute("SELECT * FROM surveys WHERE status = 'Deployed' ORDER BY created_at DESC").fetchall()
    conn.close()
    return surveys

# --- CORE FUNCTIONS ---

@st.cache_resource
def load_whisper_model():
    """Loads the Whisper model and caches it in Streamlit's resource cache."""
    import whisper
    st.info("Loading speech recognition model (this happens once)...")
    model = whisper.load_model("base")
    st.success("Speech recognition model loaded.")
    return model

def text_to_speech(text, lang='en', slow=False):
    """
    Converts text to speech. Checks for a cached version first.
    If not found, generates audio using gTTS, saves it to the cache,
    and then returns the audio data.
    """
    cache_dir = "tts_cache"
    file_hash = hashlib.md5((text + lang + str(slow)).encode('utf-8')).hexdigest()
    cached_file_path = os.path.join(cache_dir, f"{file_hash}.mp3")

    if os.path.exists(cached_file_path):
        with open(cached_file_path, "rb") as f:
            return f.read()
    else:
        try:
            tts = gTTS(text=text, lang=lang, slow=slow)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            audio_data = fp.read()
            with open(cached_file_path, "wb") as f:
                f.write(audio_data)
            return audio_data
        except Exception as e:
            st.error(f"Failed to generate TTS audio for '{text}': {e}")
            return None


def generate_survey_script(questions_json, script_path):
    """
    Generates a full conversational script from survey questions.
    """
    script = []
    progress_bar = st.progress(0, text="Generating conversational script...")

    for i, question_data in enumerate(questions_json):
        progress_bar.progress((i + 1) / len(questions_json), text=f"Generating script for question {i+1}/{len(questions_json)}...")
        try:
            prompt = f"""
            Create a JSON object for a conversational survey with three keys: "say", "explain", "question_key".
            "say": A friendly way to ask the question.
            "explain": A more detailed explanation.
            "question_key": The original question text.
            The output must be a single, valid JSON object.
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
                raise ValueError("LLM response missing keys.")
        except (ValueError, json.JSONDecodeError, Exception) as e:
            st.warning(f"Failed to generate script for a question ({e}). Using default.")
            script.append({
                "say": question_data['question'],
                "explain": question_data.get('description', 'No further details.'),
                "question_key": question_data['question']
            })

    progress_bar.empty()
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=4)
    return script

def extract_answer_from_text(question, text):
    """Uses an LLM to extract a concise answer from transcribed text."""
    try:
        prompt = f"""
        Extract the direct answer from the user's response to the survey question.
        - Ratings: Extract the number.
        - Yes/No: Extract "Yes" or "No".
        - Open-ended: Provide a concise summary.
        Respond with ONLY the extracted answer.
        Question: "{question}"
        User's Response: "{text}"
        Extracted Answer:
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        st.warning(f"LLM extraction failed: {e}. Using raw text.")
        return text

def record_audio(duration=5, sample_rate=44100):
    """Records audio and returns the file path."""
    audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
    sd.wait()
    session_audio_dir = Path("temp_audio") / st.session_state.session_id
    session_audio_dir.mkdir(exist_ok=True)
    file_path = session_audio_dir / f"answer_{st.session_state.current_step}.wav"
    sf.write(file_path, audio_data, sample_rate)
    return str(file_path)

# --- STREAMLIT UI ---

def inject_custom_css():
    """Injects CSS to create a fixed, centered, non-scrolling layout."""
    st.markdown("""
        <style>
            /* Make the main app container take up the full screen height and prevent scrolling */
            html, body, .stApp {
                height: 100vh;
                overflow: hidden;
            }
            
            /* Use flexbox to center the main content block */
            .main .block-container {
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                height: 100%;
                padding: 1rem;
            }

            /* Style for the avatar image to make it large and centered */
            div[data-testid="stImage"] img {
                width: 300px;  /* Set a large, fixed width */
                height: 300px; /* Set a large, fixed height */
                object-fit: contain;
                border-radius: 50%; /* Make it a circle */
                box-shadow: 0 8px 24px rgba(0,0,0,0.15);
                margin-bottom: 2rem; /* Add space below the avatar */
            }
            
            /* Center text elements */
            h1, .stsubheader {
                text-align: center;
            }

            /* Ensure button container has a max-width */
            div[data-testid="stHorizontalBlock"] {
                width: 100%;
                max-width: 450px;
            }
        </style>
    """, unsafe_allow_html=True)

def initialize_session_state():
    """Initializes all necessary session state variables."""
    if 'page' not in st.session_state:
        st.session_state.page = "setup"
    if 'survey_paused' not in st.session_state:
        st.session_state.survey_paused = False
    if 'avatar_state' not in st.session_state:
        st.session_state.avatar_state = 'static'
    if 'survey_flow_state' not in st.session_state:
        st.session_state.survey_flow_state = 'asking'

def render_setup_page():
    """Renders the initial setup form."""
    st.header("Step 1: Setup Your Survey Session")
    if not Path(AVATAR_ANIMATED_PATH).is_file() or not Path(AVATAR_STATIC_PATH).is_file():
        st.error(f"Avatar files not found! Make sure '{AVATAR_ANIMATED_PATH}' and '{AVATAR_STATIC_PATH}' are present.")
        st.stop()

    surveys = get_all_surveys()
    if not surveys:
        st.warning("No deployed surveys found.")
        return

    survey_options = {f"{s['id']}: {s['title']}": s for s in surveys}
    with st.form("setup_form"):
        name = st.text_input("Your Name")
        language = st.selectbox("Select Language", options=['en', 'hi'], format_func=lambda x: "English" if x == 'en' else "हिंदी")
        selected_survey_title = st.selectbox("Select a Survey", options=survey_options.keys())
        submitted = st.form_submit_button("Start Survey")

        if submitted and name and selected_survey_title:
            st.session_state.update({
                'name': name, 'language': language,
                'selected_survey': survey_options[selected_survey_title],
                'session_id': str(uuid.uuid4()), 'page': 'survey',
                'current_step': 0, 'recorded_answers': []
            })
            initialize_session_state() # Ensure all states are set for the new survey

            survey_id = st.session_state.selected_survey['id']
            script_path = Path("survey_scripts") / f"script_{survey_id}.json"

            try:
                if script_path.exists():
                    with st.spinner("Loading survey script..."):
                        script = json.loads(script_path.read_text(encoding='utf-8'))
                else:
                    json_path = st.session_state.selected_survey['json_path']
                    questions_json = json.loads(Path(json_path).read_text(encoding='utf-8'))
                    script = generate_survey_script(questions_json, str(script_path))

                if not script:
                    st.error("Could not load or generate the survey script.")
                    return

                st.session_state.script = script
                with st.spinner("Preparing survey audio..."):
                    audio_paths = {}
                    session_audio_dir = Path("temp_audio") / st.session_state.session_id
                    session_audio_dir.mkdir(exist_ok=True)
                    for i, step in enumerate(script):
                        say_audio = text_to_speech(step['say'], language)
                        explain_audio = text_to_speech(step['explain'], language)
                        say_path = session_audio_dir / f"say_{i}.mp3"
                        explain_path = session_audio_dir / f"explain_{i}.mp3"
                        if say_audio: say_path.write_bytes(say_audio)
                        if explain_audio: explain_path.write_bytes(explain_audio)
                        audio_paths[i] = {"say": str(say_path), "explain": str(explain_path)}
                    st.session_state.audio_paths = audio_paths
                st.rerun()

            except Exception as e:
                st.error(f"Failed to load or process survey: {e}")
        elif submitted:
            st.error("Please provide your name and select a survey.")

def render_survey_page():
    """Renders the automated, avatar-driven survey interface."""
    step_index = st.session_state.current_step
    script = st.session_state.script

    if step_index >= len(script):
        st.session_state.page = "processing"
        st.rerun()
        return

    current_step_data = script[step_index]
    question_to_say = current_step_data['say']

    # --- Main Display (CSS handles layout) ---
    st.subheader(f"Question {step_index + 1}/{len(script)}")
    
    if st.session_state.avatar_state == 'playing':
        st.image(AVATAR_ANIMATED_PATH)
    else:
        st.image(AVATAR_STATIC_PATH)

    st.title(question_to_say)

    # --- Controls ---
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.survey_paused:
            if st.button("▶️ Resume Survey", use_container_width=True):
                st.session_state.survey_paused = False
                st.rerun()
        else:
            if st.button("⏸️ Pause Survey", use_container_width=True):
                st.session_state.survey_paused = True
                st.rerun()
    with col2:
        if st.button("💡 Explain Question", use_container_width=True):
            st.session_state.avatar_state = 'playing'
            st.audio(st.session_state.audio_paths[step_index]['explain'], autoplay=True)
            st.info(current_step_data['explain'])
            st.rerun()
    
    # --- Automation Flow ---
    if st.session_state.survey_paused:
        st.warning("Survey is paused. Press Resume to continue.")
        st.stop()

    flow_state = st.session_state.survey_flow_state
    
    if flow_state == 'asking':
        st.session_state.avatar_state = 'playing'
        st.audio(st.session_state.audio_paths[step_index]['say'], autoplay=True)
        st.session_state.survey_flow_state = 'countdown'
        time.sleep(3) # Approximation for audio playback time
        st.rerun()

    elif flow_state == 'countdown':
        st.session_state.avatar_state = 'static'
        st.subheader("Get ready to answer...")
        countdown_placeholder = st.empty()
        for i in range(5, 0, -1):
            countdown_placeholder.metric("Recording in...", f"{i} seconds")
            time.sleep(1)
        countdown_placeholder.empty()
        st.session_state.survey_flow_state = 'recording'
        st.rerun()

    elif flow_state == 'recording':
        st.session_state.avatar_state = 'static'
        st.info("🎙️ Recording your answer now...")
        audio_path = record_audio(duration=5)
        st.session_state.recorded_answers.append(audio_path)
        st.success(f"Answer for question {step_index + 1} recorded!")
        st.session_state.current_step += 1
        st.session_state.survey_flow_state = 'asking'
        time.sleep(1)
        st.rerun()

def render_processing_page():
    """Processes all recorded answers after the survey."""
    model = load_whisper_model()
    st.header("Survey Complete!")
    st.info("Thank you! Processing your answers...")
    final_answers = {}
    progress_bar = st.progress(0, text="Starting processing...")

    for i, audio_path in enumerate(st.session_state.recorded_answers):
        progress_bar.progress((i + 1) / len(st.session_state.recorded_answers), text=f"Processing answer {i+1}...")
        try:
            question_key = st.session_state.script[i]['question_key']
            result = model.transcribe(audio_path, fp16=False)
            transcribed_text = result["text"].strip()
            extracted_answer = extract_answer_from_text(question_key, transcribed_text)
            final_answers[question_key] = extracted_answer
        except Exception as e:
            st.error(f"Could not process answer {i+1}: {e}")
            final_answers[question_key] = "ERROR - PROCESSING FAILED"

    progress_bar.empty()
    st.success("✅ All answers processed!")
    st.subheader("Final Results:")
    st.json(final_answers)

    if st.button("Submit Results to Server"):
        with st.spinner("Submitting..."):
            try:
                api_url = f"http://127.0.0.1:8000/submit/{st.session_state.selected_survey['id']}"
                response = requests.post(api_url, json=final_answers)
                response.raise_for_status()
                st.success("Results submitted successfully!")
            except Exception as e:
                st.error(f"Failed to submit results via API: {e}")

    if st.button("Start New Survey"):
        shutil.rmtree(Path("temp_audio") / st.session_state.session_id, ignore_errors=True)
        for key in list(st.session_state.keys()):
            if key != 'webrtc_contexts':
                del st.session_state[key]
        st.rerun()

# --- Main App Logic ---
def main():
    """Main function to run the Streamlit app."""
    st.set_page_config(page_title="Voice Survey Avatar", layout="wide")
    inject_custom_css()
    initialize_session_state()

    if st.session_state.page == "setup":
        st.title("🎙️ Voice Survey Portal")
        render_setup_page()
    elif st.session_state.page == "survey":
        render_survey_page()
    elif st.session_state.page == "processing":
        render_processing_page()

if __name__ == "__main__":
    main()
