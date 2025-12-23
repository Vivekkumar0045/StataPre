# Streamlit Secrets Configuration Guide

## Setup Instructions

### 1. Configure Streamlit Secrets

Open `.streamlit/secrets.toml` file and add your credentials:
```toml
GOOGLE_API_KEY = "your-actual-google-api-key-here"
SUPABASE_URL = "your-supabase-project-url"
SUPABASE_KEY = "your-supabase-anon-key"
```

### 2. Setup Supabase Database

1. Go to your Supabase project dashboard
2. Navigate to SQL Editor
3. Run the SQL script from `supabase_schema.sql` file to create all tables
4. Copy your project URL and anon/public key from Settings > API

### 3. Run the App

Run the app: `streamlit run app.py`

## Security Notes

⚠️ **Important:**
- Never commit `.streamlit/secrets.toml` to version control
- The file is already in `.gitignore`
- Keep your API keys secure and private
- Use Supabase Row Level Security (RLS) policies for production

## Deploying to Streamlit Cloud

When deploying to Streamlit Cloud:
1. Go to your app settings
2. Navigate to "Secrets" section
3. Add your secrets in TOML format:
   ```toml
   GOOGLE_API_KEY = "your-actual-api-key-here"
   SUPABASE_URL = "your-supabase-project-url"
   SUPABASE_KEY = "your-supabase-anon-key"
   ```

## How It Works

- `app.py` loads credentials from Streamlit secrets
- Connects to Supabase for cloud database storage
- All data is stored securely in Supabase PostgreSQL database
- API key is set as environment variable for child modules (`ds_r1.py` and `adhr.py`)
