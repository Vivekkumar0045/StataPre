import pandas as pd
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn
import requests
from datetime import datetime
from supabase import create_client, Client

# --- SETUP ---
app = FastAPI()

# Load Supabase credentials from environment variables or config
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://fmvpeaqtwgjsyktnjpfa.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_BdqDQJZ3UTt8thycysxDkQ_vdoYG6J8")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# This is crucial for allowing the HTML file (opened from your local file system)
# to communicate with this server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- HELPER FUNCTIONS ---
def get_geolocation(ip_address: str):
    """Gets geolocation data from a free API based on IP address."""
    if not ip_address or ip_address == "127.0.0.1":
        return {"city": "Local", "country": "N/A"}
    try:
        response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=5)
        response.raise_for_status()
        data = response.json()
        return {
            "city": data.get("city", "Unknown"),
            "country": data.get("country", "Unknown")
        }
    except Exception as e:
        print(f"Geolocation lookup failed: {e}")
        return {"city": "Error", "country": "Error"}

# --- API ROUTES ---
@app.get("/form/{survey_id}", response_class=HTMLResponse)
async def serve_form(survey_id: int):
    """Serves the specific HTML form for a survey."""
    form_path = os.path.join("shareable_forms", f"survey_{survey_id}", "form.html")
    if not os.path.exists(form_path):
        raise HTTPException(status_code=404, detail="Survey form not found.")
    return FileResponse(form_path)

@app.post("/submit/{survey_id}")
async def handle_submission(survey_id: int, request: Request):
    """
    Handles a new survey submission and saves it directly to Supabase database.
    """
    data = await request.json()
    
    try:
        # --- Capture Metadata ---
        ip_address = request.client.host
        location_data = get_geolocation(ip_address)
        
        # Separate metadata from the actual survey answers
        metadata_keys = ['start_time', 'end_time', 'device_info', 'geo_latitude', 'geo_longitude']
        metadata = {key: data.pop(key, None) for key in metadata_keys}
        answers = data  # The rest of the data is the answers

        # 1. Create a new respondent entry with all collected metadata
        respondent_data = {
            "survey_id": survey_id,
            "name": "Web Respondent",  # A generic name for submissions from the web form
            "start_time": metadata.get('start_time'),
            "end_time": metadata.get('end_time'),
            "device_info": metadata.get('device_info'),
            "geo_latitude": metadata.get('geo_latitude'),
            "geo_longitude": metadata.get('geo_longitude'),
            "ip_address": ip_address,
            "ip_city": location_data['city'],
            "ip_country": location_data['country']
        }
        
        respondent_response = supabase.table("respondents").insert(respondent_data).execute()
        respondent_id = respondent_response.data[0]['id']

        # 2. Insert each answer into the answers table, linked to the new respondent
        answers_data = [
            {
                "respondent_id": respondent_id,
                "question": question,
                "answer": str(answer)
            }
            for question, answer in answers.items()
        ]
        
        supabase.table("answers").insert(answers_data).execute()
        
        return {"message": "Submission successful"}
    except Exception as e:
        print(f"Error processing submission: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save submission: {e}")

if __name__ == "__main__":
    print("Starting FastAPI server for survey submissions...")
    print("Run this file in a separate terminal.")
    print("API will be available at http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
