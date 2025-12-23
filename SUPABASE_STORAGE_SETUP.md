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
   
   **Option A: Using SQL Editor (Recommended)**
   
   Go to SQL Editor in Supabase Dashboard and run these commands:
   
   ```sql
   -- Policy 1: Allow anyone to upload HTML forms
   CREATE POLICY "Allow public uploads to survey-forms"
   ON storage.objects FOR INSERT
   WITH CHECK (
     bucket_id = 'survey-forms'
     AND storage.extension(name) = 'html'
     AND auth.role() = 'anon'
   );

   -- Policy 2: Allow anyone to read HTML forms
   CREATE POLICY "Allow public reads from survey-forms"
   ON storage.objects FOR SELECT
   USING (
     bucket_id = 'survey-forms'
     AND storage.extension(name) = 'html'
   );

   -- Policy 3: Allow updating existing forms (for upsert)
   CREATE POLICY "Allow public updates to survey-forms"
   ON storage.objects FOR UPDATE
   USING (
     bucket_id = 'survey-forms'
     AND storage.extension(name) = 'html'
   )
   WITH CHECK (
     bucket_id = 'survey-forms'
     AND storage.extension(name) = 'html'
     AND auth.role() = 'anon'
   );
   ```
   
   **Option B: Disable RLS (Easiest)**
   - Click on the `survey-forms` bucket
   - Go to "Policies" tab
   - Click "Disable RLS" or click the three dots → "Edit bucket" → Uncheck "Enable RLS"
   
   **Option C: Create Upload Policy via Dashboard (Manual)**
   - Click on the `survey-forms` bucket
   - Go to "Policies" tab
   - Click "New Policy" → "Custom policy"
   - **Upload Policy:**
     - Policy name: `Allow public uploads`
     - Operation: `INSERT`
     - Target roles: `public` or `anon`
     - WITH CHECK expression: `bucket_id = 'survey-forms' AND storage.extension(name) = 'html'`
   - **Read Policy:**
     - Policy name: `Allow public reads`
     - Operation: `SELECT`
     - Target roles: `public` or `anon`
     - USING expression: `bucket_id = 'survey-forms' AND storage.extension(name) = 'html'`
   - **Update Policy (for upsert):**
     - Policy name: `Allow public updates`
     - Operation: `UPDATE`
     - Target roles: `public` or `anon`
     - USING/WITH CHECK expression: `bucket_id = 'survey-forms' AND storage.extension(name) = 'html'`

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
