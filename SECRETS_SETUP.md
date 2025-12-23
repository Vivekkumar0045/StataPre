# Streamlit Secrets Configuration Guide

## Setup Instructions

### Using Streamlit Secrets

1. Open `.streamlit/secrets.toml` file
2. Replace `YOUR_API_KEY_HERE` with your actual Google API key:
   ```toml
   GOOGLE_API_KEY = "your-actual-api-key-here"
   ```
3. Save the file
4. Run the app: `streamlit run app.py`

## Security Notes

⚠️ **Important:**
- Never commit `.streamlit/secrets.toml` to version control
- The file is already in `.gitignore`
- Keep your API keys secure and private

## Deploying to Streamlit Cloud

When deploying to Streamlit Cloud:
1. Go to your app settings
2. Navigate to "Secrets" section
3. Add your secrets in TOML format:
   ```toml
   GOOGLE_API_KEY = "your-actual-api-key-here"
   ```

## How It Works

- `app.py` loads the API key from Streamlit secrets
- The API key is then set as an environment variable for child modules (`ds_r1.py` and `adhr.py`)
- All modules use the same API key automatically
