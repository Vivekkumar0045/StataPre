import streamlit as st
import pandas as pd
import json
import os
import time
from datetime import datetime
from ollama import Client


from ds_r1 import generate_survey_design
from adhr import extract_and_process

client = Client(host='http://localhost:11434')

st.set_page_config(
    page_title="Dynamic Survey Tool",
    page_icon="📋",
    layout="wide"
)

st.markdown("""
<style>
    .header {
        color: #1e3a8a;
        border-bottom: 2px solid #1e3a8a;
        padding-bottom: 10px;
    }
    .section {
        padding: 20px;
        border-radius: 10px;
        background-color: #f0f8ff;
        margin-bottom: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .stButton>button {
        background-color: #1e3a8a;
        color: white;
        border-radius: 5px;
        padding: 10px 24px;
        font-weight: bold;
    }
    .stProgress>div>div>div {
        background-color: #1e3a8a;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.title("📋 Dynamic Survey Tool")
    st.markdown("---")
    
    # Initialize session state variables
    if 'survey_generated' not in st.session_state:
        st.session_state.survey_generated = False
    if 'aadhaar_verified' not in st.session_state:
        st.session_state.aadhaar_verified = False
    if 'survey_path' not in st.session_state:
        st.session_state.survey_path = {}
    if 'aadhaar_data' not in st.session_state:
        st.session_state.aadhaar_data = None
    if 'survey_responses' not in st.session_state:
        st.session_state.survey_responses = {}
    if 'current_question' not in st.session_state:
        st.session_state.current_question = 0

    # Section 1: Survey Generation
    with st.container():
        st.markdown("<h2 class='header'>Step 1: Create Survey</h2>", unsafe_allow_html=True)
        
        query = st.text_area(
            "Enter survey requirements:",
            value="Design a resident satisfaction survey for a housing complex. Include questions on housing quality, amenities, community services, and safety.",
            height=100,
            key="survey_query"
        )
        
        if st.button("Generate Survey Design"):
            with st.spinner("Creating survey design..."):
                try:
                    # This function is expected to create 'survey_responses/data.csv' and 'data.txt'
                    generate_survey_design(query)
                    
                    # --- FINAL FIX ---
                    # Define the expected static file paths
                    csv_path = os.path.join("survey_responses", "data.csv")
                    txt_path = os.path.join("survey_responses", "data.txt")

                    # Check if the main CSV file was actually created by the function
                    if not os.path.exists(csv_path):
                        st.error("Survey file generation failed. The function did not create 'data.csv' in the 'survey_responses' folder.")
                        st.stop()

                    # If the file exists, save the static paths to the session state
                    st.session_state.survey_path = {
                        'csv': csv_path,
                        'txt': txt_path
                    }
                    # --- END FINAL FIX ---
                    
                    st.session_state.survey_generated = True
                    st.success("Survey generated successfully!")
                    st.rerun() 
                    
                except Exception as e:
                    st.error(f"Error during survey generation: {str(e)}")
    
    # Display survey results if generated
    if st.session_state.survey_generated:
        with st.container():
            st.markdown("<h2 class='header'>Survey Design</h2>", unsafe_allow_html=True)
            
            try:
                survey_df = pd.read_csv(st.session_state.survey_path['csv'])
                st.subheader("Survey Questions")
                st.dataframe(survey_df, height=300, use_container_width=True)
                st.session_state.survey_columns = survey_df.columns.tolist()
            except Exception as e:
                st.error(f"Error loading survey CSV: {str(e)}")
            
            try:
                with open(st.session_state.survey_path['txt'], 'r') as f:
                    survey_text = f.read()
                st.subheader("Survey Details")
                st.text_area("Survey Description", value=survey_text, height=200)
            except FileNotFoundError:
                st.info("No text description file ('data.txt') was found for this survey.")
            except Exception as e:
                st.error(f"Error loading survey text: {str(e)}")

    # Section 2: Respondent Identification
    if st.session_state.survey_generated and not st.session_state.aadhaar_verified:
        with st.container():
            st.markdown("<h2 class='header'>Step 2: Respondent Identification</h2>", unsafe_allow_html=True)
            
            identification_method = st.radio(
                "Choose identification method:",
                ["Aadhaar Card Scan", "Manual Entry"],
                horizontal=True
            )
            
            if identification_method == "Aadhaar Card Scan":
                aadhaar_file = st.file_uploader("Upload Aadhaar Card Image (JPG/PNG)", type=["jpg", "jpeg", "png"])
                
                if aadhaar_file:
                    if st.button("Process Aadhaar"):
                        with st.spinner("Extracting Aadhaar details..."):
                            try:
                                with open("temp_aadhaar.jpg", "wb") as f:
                                    f.write(aadhaar_file.getbuffer())
                                extract_and_process("temp_aadhaar.jpg")
                                with open("aadhaar_output.json", "r") as f:
                                    st.session_state.aadhaar_data = json.load(f)
                                st.success("Aadhaar processed successfully! Please verify details below.")
                            except Exception as e:
                                st.error(f"Error processing Aadhaar: {str(e)}")

            else: # Manual Entry
                with st.form("manual_identification"):
                    st.subheader("Enter Respondent Information")
                    name = st.text_input("Full Name")
                    dob = st.text_input("Date of Birth (DD/MM/YYYY)")
                    gender = st.selectbox("Gender", ["Male", "Female", "Other", "Prefer not to say"])
                    contact = st.text_input("Contact Number")
                    address = st.text_area("Address")
                    
                    if st.form_submit_button("Confirm Information"):
                        if not all([name, dob, address]):
                            st.warning("Please fill out Name, Date of Birth, and Address.")
                        else:
                            st.session_state.aadhaar_data = {
                                "name": name, "dob": dob, "gender": gender,
                                "aadhaar_number": "MANUAL_ENTRY", "address": address, "contact": contact
                            }
                            st.session_state.aadhaar_verified = True
                            st.success("Information saved! Proceeding to survey...")
                            st.rerun()

            # Display Aadhaar verification popup (if data is loaded from scan)
            if st.session_state.aadhaar_data and not st.session_state.aadhaar_verified and identification_method == "Aadhaar Card Scan":
                with st.expander("Verify Aadhaar Details", expanded=True):
                    st.json(st.session_state.aadhaar_data)
                    col1, col2, _ = st.columns([1, 1, 5])
                    with col1:
                        if st.button("Confirm Details"):
                            st.session_state.aadhaar_verified = True
                            st.success("Aadhaar verified! Proceeding to survey...")
                            st.rerun()
                    with col2:
                        if st.button("Re-upload"):
                            st.session_state.aadhaar_data = None
                            st.rerun()

    # Section 3: Survey Response Collection
    if st.session_state.aadhaar_verified:
        with st.container():
            st.markdown("<h2 class='header'>Step 3: Complete Survey</h2>", unsafe_allow_html=True)
            
            if not st.session_state.survey_responses:
                st.session_state.survey_responses = {
                    "Full Name": st.session_state.aadhaar_data.get("name", ""),
                    "Date of Birth": st.session_state.aadhaar_data.get("dob", ""),
                    "Gender": st.session_state.aadhaar_data.get("gender", ""),
                    "Contact Number": st.session_state.aadhaar_data.get("contact", ""),
                    "Address": st.session_state.aadhaar_data.get("address", ""),
                    "Aadhaar Number": st.session_state.aadhaar_data.get("aadhaar_number", "")
                }
            
            id_fields = ["Full Name", "Date of Birth", "Gender", "Aadhaar Number", "Contact Number", "Address"]
            remaining_questions = [col for col in st.session_state.survey_columns if col not in id_fields]
            
            if remaining_questions and st.session_state.current_question < len(remaining_questions):
                current_q = remaining_questions[st.session_state.current_question]
                
                prompt = f"Generate a clear, single survey question about: '{current_q}'. Phrase it conversationally and keep it concise."
                try:
                    response = client.generate(model='gemma:2b', prompt=prompt)
                    question_text = response['response'].strip().replace('"', '')
                except Exception:
                    question_text = f"Please provide your feedback on: {current_q}"
                
                st.subheader(f"Question {st.session_state.current_question + 1}/{len(remaining_questions)}")
                st.markdown(f"**{question_text}**")
                
                user_response_key = f"q_{st.session_state.current_question}"
                if any(word in current_q.lower() for word in ["rating", "scale"]):
                    user_response = st.slider("Your response (1=Very Poor, 5=Very Good):", 1, 5, 3, key=user_response_key)
                elif any(word in current_q.lower() for word in ["agree", "satisfied"]):
                    user_response = st.radio("Your response:", ["Strongly Agree", "Agree", "Neutral", "Disagree", "Strongly Disagree"], key=user_response_key, horizontal=True)
                else:
                    user_response = st.text_input("Your response:", key=user_response_key)
                
                if st.button("Next Question"):
                    if str(user_response):
                        st.session_state.survey_responses[current_q] = str(user_response)
                        st.session_state.current_question += 1
                        st.rerun()
                    else:
                        st.warning("Please provide a response before proceeding.")
            else:
                st.success("All questions answered!")
                st.subheader("Review Your Responses")
                
                final_responses = st.session_state.survey_responses.copy()
                for col in st.session_state.survey_columns:
                    if col not in final_responses:
                        final_responses[col] = "N/A"

                review_df = pd.DataFrame([final_responses])[st.session_state.survey_columns]
                st.dataframe(review_df, use_container_width=True)
                
                if st.button("Submit Survey"):
                    try:
                        csv_path = st.session_state.survey_path['csv']
                        header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
                        
                        # Since the survey design is static (data.csv), we append responses to a different file
                        # to avoid mixing design rows with response rows.
                        response_file_path = os.path.join("survey_responses", "responses.csv")
                        
                        header = not os.path.exists(response_file_path) or os.path.getsize(response_file_path) == 0
                        review_df.to_csv(response_file_path, mode='a', header=header, index=False)
                        
                        st.balloons()
                        st.success("Survey response submitted successfully to 'responses.csv'!")
                        
                        time.sleep(3)
                        # Clean up for the next respondent, but keep the generated survey state
                        keys_to_reset = ['aadhaar_verified', 'aadhaar_data', 'survey_responses', 'current_question']
                        for key in keys_to_reset:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error saving response: {str(e)}")

if __name__ == "__main__":
    os.makedirs("survey_responses", exist_ok=True)
    main()

