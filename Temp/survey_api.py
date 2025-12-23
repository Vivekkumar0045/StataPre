# survey_api.py

import pandas as pd
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# --- Configuration ---
SURVEY_RESPONSES_DIR = "survey_responses"
CSV_PATH = os.path.join(SURVEY_RESPONSES_DIR, "data.csv")

# --- FastAPI App Initialization ---
app = FastAPI()

# Add CORS middleware to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Check if the CSV file exists on startup."""
    if not os.path.exists(CSV_PATH):
        print(f"FATAL ERROR: The survey data file '{CSV_PATH}' does not exist. Please generate it using the admin portal.")
        raise FileNotFoundError(f"'{CSV_PATH}' not found. The API cannot collect data.")
    print("FastAPI server started. Ready to collect responses.")
    print(f"Data will be saved to: {CSV_PATH}")


@app.post("/submit")
async def submit_survey_response(request: Request):
    """
    Receives survey data as form data and appends it to the CSV file.
    """
    try:
        response_data = await request.form()
        response_dict = dict(response_data)
        
        df = pd.read_csv(CSV_PATH)
        new_row = pd.DataFrame([response_dict], columns=df.columns)
        
        new_row.to_csv(CSV_PATH, mode='a', header=False, index=False)

        print(f"Successfully saved response: {response_dict}")
        return {"message": "Survey response saved successfully!", "data": response_dict}

    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"Survey data file not found at '{CSV_PATH}'.")
    except Exception as e:
        print(f"An error occurred while saving the response: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")


@app.get("/")
def read_root():
    return {"message": "Survey API is running. Send POST requests to /submit to save data."}