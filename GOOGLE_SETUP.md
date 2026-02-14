# Google Sheets Setup Guide for NOVA II

This guide will help you set up Google OAuth credentials to allow NOVA II to access your Google Sheets.

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name it "NOVA II" or similar
4. Click "Create"

## Step 2: Enable Google Sheets API

1. In your project, go to "APIs & Services" → "Library"
2. Search for "Google Sheets API"
3. Click on it and press "Enable"

## Step 3: Create OAuth Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "+ CREATE CREDENTIALS" → "OAuth client ID"
3. If prompted, configure OAuth consent screen:
   - User Type: External
   - App name: "NOVA II"
   - User support email: your email
   - Developer contact: your email
   - Click "Save and Continue" through the steps
4. Back in Credentials, click "+ CREATE CREDENTIALS" → "OAuth client ID"
5. Application type: "Desktop app"
6. Name: "NOVA II Desktop"
7. Click "Create"

## Step 4: Download Credentials

1. Click the download icon (⬇) next to your newly created OAuth 2.0 Client ID
2. Save the file as `credentials.json`
3. Move `credentials.json` to your project directory:
   ```
   /Users/benpoovaviranon/Desktop/Ben/AI & Automation/NOVA II/credentials.json
   ```

## Step 5: Update .env File

Add your Google Sheet ID to the `.env` file:

```bash
# Google Sheets Configuration
GOOGLE_SHEET_ID=194ZhTkYYog4qHGALr0qSYuX4iXvuypELRKoVz_--3DA
```

The Sheet ID is already set to your NOVA II sheet by default.

## Step 6: Run Initialization

```bash
cd "/Users/benpoovaviranon/Desktop/Ben/AI & Automation/NOVA II"
source venv/bin/activate
python execution/initialize_sheets.py
```

On first run:
1. A browser window will open
2. Sign in with your Google account
3. Click "Allow" to grant access
4. The script will create a `token.pickle` file for future use

## Files Created

After setup, you'll have:
- `credentials.json` - OAuth client credentials (don't commit to git)
- `token.pickle` - Access token (don't commit to git)

Both are already in `.gitignore` for security.

## Troubleshooting

### "credentials.json not found"
- Make sure you downloaded the file and placed it in the project root
- Check the filename is exactly `credentials.json`

### "Access denied" or authentication errors
- Make sure you're using the same Google account that owns the Sheet
- Try deleting `token.pickle` and re-authenticating

### "API has not been used in project"
- Wait a few minutes after enabling the API
- Make sure Google Sheets API is enabled in your Cloud Console project

## Security Notes

- Never commit `credentials.json` or `token.pickle` to version control
- These files contain sensitive information
- They're already in `.gitignore`
