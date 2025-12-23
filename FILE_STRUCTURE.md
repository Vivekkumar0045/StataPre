# 📁 Project File Structure

## Organized Folders

### 📦 assets/

Contains all media files and machine learning models:

- `aadhar.jpg` - Sample Aadhaar card image
- `avatar.gif` - Animated avatar for UI
- `avatar_static.png` - Static avatar image
- `devquery.txt` - Development query template
- `model.pkl` - Machine learning model for filename prediction

### 📋 json_data/

Contains all JSON configuration files:

- `classify.json` - Survey classification data
- `config.json` - Application configuration (admin credentials)
- `lang.json` - Localization/translation data

### 📊 survey_responses/

Generated survey response files (CSV, TXT, JSON)

### 📄 survey_jsons/

Generated survey question JSON files

### 🌐 shareable_forms/

Generated HTML forms for surveys

### 📝 prompt_logs/

LLM prompt logging files

### 📤 uploads/

User-uploaded Aadhaar card images

### 🗃️ Temp/

Temporary files

## Main Application Files

- `app.py` - Main Streamlit application with online/offline mode
- `ds_r1.py` - Survey design generation module
- `adhr.py` - Aadhaar card processing
- `avatar.py` - Avatar animation handler
- `history.py` - History management
- `content.py` - HTML templates
- `api.py` - API endpoints for web forms
- `convert_to_pdf.py` - PDF conversion utilities

## Configuration Files

- `.env` - Environment variables (API keys)
- `survey_portal.db` - SQLite database

## Updated Path References

All code files have been updated to reference the new folder structure:

- Image files → `assets/`
- JSON files → `json_data/`
- Model files → `assets/`
