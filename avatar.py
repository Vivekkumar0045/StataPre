
import os
os.environ['STREAMLIT_SERVER_FILE_WATCHER_TYPE'] = 'none'

import streamlit as st
import numpy as np
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
import base64
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env file
load_dotenv()

# Configure Google Generative AI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_API_KEY_HERE":
    st.error("Please set GOOGLE_API_KEY in your .env file")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(model_name="gemini-3-flash-preview")

# Initialize Supabase client
try:
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://fmvpeaqtwgjsyktnjpfa.supabase.co")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_BdqDQJZ3UTt8thycysxDkQ_vdoYG6J8")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Failed to initialize Supabase: {e}")
    st.stop()

# Google Cloud API endpoints
SPEECH_API_URL = f"https://speech.googleapis.com/v1/speech:recognize?key={GOOGLE_API_KEY}"
TTS_API_URL = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_API_KEY}"

# --- PROJECT SETUP & CONFIG ---
# Create necessary directories
os.makedirs("survey_jsons", exist_ok=True)
os.makedirs("temp_audio", exist_ok=True)
os.makedirs("survey_scripts", exist_ok=True)
os.makedirs("tts_cache", exist_ok=True) # Directory for cached TTS audio

# --- AVATAR FILES ---
# User should place their avatar files in the root directory
AVATAR_ANIMATED_PATH = "assets/avatar.gif"
AVATAR_STATIC_PATH = "assets/avatar_static.png"

# --- DATABASE HELPER ---
def get_all_surveys():
    """Fetches all 'Deployed' surveys from Supabase."""
    try:
        response = supabase.table("surveys").select("*").eq("status", "Deployed").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Failed to fetch surveys from Supabase: {e}")
        return []

# --- CORE FUNCTIONS ---

def transcribe_audio_google(audio_file_path):
    """Transcribes audio using Google Speech-to-Text REST API."""
    try:
        # Read and encode audio file
        with open(audio_file_path, "rb") as audio_file:
            content = audio_file.read()
        
        audio_base64 = base64.b64encode(content).decode('utf-8')
        
        # Prepare request payload
        payload = {
            "config": {
                "encoding": "LINEAR16",
                "sampleRateHertz": 44100,
                "languageCode": "en-US",
                "alternativeLanguageCodes": ["hi-IN"],
                "enableAutomaticPunctuation": True
            },
            "audio": {
                "content": audio_base64
            }
        }
        
        # Make API request
        response = requests.post(SPEECH_API_URL, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        if "results" in result and len(result["results"]) > 0:
            return result["results"][0]["alternatives"][0]["transcript"]
        else:
            return "No speech detected"
    except Exception as e:
        st.error(f"Error transcribing audio: {e}")
        return "ERROR - TRANSCRIPTION FAILED"

def text_to_speech(text, lang='en', slow=False):
    """
    Converts text to speech using Google Text-to-Speech REST API.
    Checks for a cached version first. If not found, generates audio
    using Google TTS, saves it to the cache, and returns the audio data.
    """
    cache_dir = "tts_cache"
    file_hash = hashlib.md5((text + lang + str(slow)).encode('utf-8')).hexdigest()
    cached_file_path = os.path.join(cache_dir, f"{file_hash}.mp3")

    if os.path.exists(cached_file_path):
        with open(cached_file_path, "rb") as f:
            return f.read()
    else:
        try:
            # Configure voice parameters based on language
            if lang == 'hi':
                language_code = 'hi-IN'
                voice_name = 'hi-IN-Wavenet-A'  # High quality Hindi voice
            else:
                language_code = 'en-US'
                voice_name = 'en-US-Neural2-F'  # High quality English voice
            
            speaking_rate = 0.85 if slow else 1.0
            
            # Prepare request payload
            payload = {
                "input": {
                    "text": text
                },
                "voice": {
                    "languageCode": language_code,
                    "name": voice_name
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": speaking_rate
                }
            }
            
            # Make API request
            response = requests.post(TTS_API_URL, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Decode base64 audio content
            audio_data = base64.b64decode(result["audioContent"])
            
            # Cache the audio
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
        dev_mode = st.checkbox("🔧 Developer Mode (Only 1st & 10th questions)", value=False)
        submitted = st.form_submit_button("Start Survey")

        if submitted and name and selected_survey_title:
            st.session_state.update({
                'name': name, 'language': language,
                'selected_survey': survey_options[selected_survey_title],
                'session_id': str(uuid.uuid4()), 'page': 'survey',
                'current_step': 0, 'recorded_answers': [],
                'dev_mode': dev_mode
            })
            initialize_session_state() # Ensure all states are set for the new survey

            survey_id = st.session_state.selected_survey['id']
            script_path = Path("survey_scripts") / f"script_{survey_id}.json"

            try:
                if script_path.exists():
                    with st.spinner("Loading survey script..."):
                        script = json.loads(script_path.read_text(encoding='utf-8'))
                else:
                    # Get json_path from survey data
                    json_path = st.session_state.selected_survey.get('json_path', '')
                    
                    # Check if json_path exists and is a valid file
                    if json_path and Path(json_path).exists():
                        questions_json = json.loads(Path(json_path).read_text(encoding='utf-8'))
                    else:
                        # Try to find the JSON file in survey_jsons directory
                        survey_title = st.session_state.selected_survey['title']
                        json_files = list(Path("survey_jsons").glob("*.json"))
                        
                        if not json_files:
                            st.error("No survey JSON files found in survey_jsons directory.")
                            return
                        
                        # Use the first available JSON file or try to match by title
                        questions_json = json.loads(json_files[0].read_text(encoding='utf-8'))
                    
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
    # Check if script is initialized
    if 'script' not in st.session_state or 'audio_paths' not in st.session_state:
        st.error("Survey not properly initialized. Returning to setup...")
        st.session_state.page = "setup"
        time.sleep(2)
        st.rerun()
        return
    
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
        
        # Check if in dev mode and should skip this question
        dev_mode = st.session_state.get('dev_mode', False)
        should_skip = dev_mode and (step_index != 0 and step_index != 9)  # Skip all except 1st (index 0) and 10th (index 9)
        
        if should_skip:
            # Create a dummy audio file with "no speech detected"
            st.info("🔧 DEV MODE: Skipping question...")
            session_audio_dir = Path("temp_audio") / st.session_state.session_id
            session_audio_dir.mkdir(exist_ok=True)
            dummy_audio_path = session_audio_dir / f"answer_{step_index}.wav"
            # Create a minimal silent audio file
            silence = np.zeros(int(0.1 * 44100), dtype='float32')
            sf.write(dummy_audio_path, silence, 44100)
            st.session_state.recorded_answers.append(str(dummy_audio_path))
            st.session_state.current_step += 1
            st.session_state.survey_flow_state = 'asking'
            time.sleep(0.3)  # Faster in dev mode
            st.rerun()
        else:
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
    st.header("Survey Complete!")
    st.info("Thank you! Processing your answers...")
    final_answers = {}
    progress_bar = st.progress(0, text="Starting processing...")

    for i, audio_path in enumerate(st.session_state.recorded_answers):
        progress_bar.progress((i + 1) / len(st.session_state.recorded_answers), text=f"Processing answer {i+1}...")
        try:
            question_key = st.session_state.script[i]['question_key']
            transcribed_text = transcribe_audio_google(audio_path)
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
