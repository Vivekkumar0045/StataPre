# Supabase Storage Setup for Survey Forms

## Steps to Create Storage Bucket

1. **Go to Supabase Dashboard**
   - Visit: https://supabase.com/dashboard
   - Select your project: `fmvpeaqtwgjsyktnjpfa`

2. **Navigate to Storage**
   - Click on "Storage" in the left sidebar
   - Click "New bucket" button

3. **Create New Bucket**
   - Bucket name: `survey-forms`
   - Public bucket: ✅ **Enable** (toggle ON)
   - Click "Create bucket"

4. **Configure RLS Policies (IMPORTANT)**
   
   After creating the bucket, you need to set up Row Level Security policies:
   
   **Option A: Disable RLS (Easiest - Recommended)**
   - Click on the `survey-forms` bucket
   - Go to "Policies" tab
   - Click "Disable RLS" or click the three dots → "Edit bucket" → Uncheck "Enable RLS"
   
   **Option B: Create Upload Policy (More Secure)**
   - Click on the `survey-forms` bucket
   - Go to "Policies" tab
   - Click "New Policy"
   - Choose "Custom policy"
   - Policy name: `Allow public uploads`
   - Operation: `INSERT`
   - Target roles: `public`
   - USING expression: `true`
   - Click "Review" → "Save policy"
   
   Then create a read policy:
   - Click "New Policy"
   - Policy name: `Allow public reads`
   - Operation: `SELECT`
   - Target roles: `public`
   - USING expression: `true`
   - Click "Review" → "Save policy"

5. **Verify Bucket Settings**
   - The bucket should be publicly accessible
   - RLS should be disabled OR policies should allow public access
   - Anyone with the URL can view the HTML forms
   - Forms will be accessible at: `https://fmvpeaqtwgjsyktnjpfa.supabase.co/storage/v1/object/public/survey-forms/survey_X_form.html`

## How It Works

When you click "🔗 Share Form" in the app:
1. HTML form is generated locally
2. Uploaded to Supabase Storage bucket `survey-forms`
3. Public URL is generated automatically
4. You can share this URL via email, WhatsApp, SMS, etc.
5. Anyone with the link can fill the survey
6. Responses are submitted to your API at https://vivek45537-kartavya.hf.space

## Benefits

✅ No file downloads needed
✅ Direct shareable links
✅ Works perfectly on Streamlit Cloud
✅ Forms hosted reliably on Supabase
✅ Automatic public URL generation
✅ Easy to share via any channel
