import os
import pickle
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]
DEFAULT_SHEET_ID = '194ZhTkYYog4qHGALr0qSYuX4iXvuypELRKoVz_--3DA'

import base64

def get_credentials():
    """Get or refresh Google API credentials."""
    creds = None
    
    # 1. Try reading from environment variable (JSON string)
    token_json = os.getenv('GOOGLE_TOKEN_JSON')
    if token_json:
        try:
            print("🔑 Attempting to load credentials from GOOGLE_TOKEN_JSON...")
            creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
            print("✅ Successfully loaded credentials from GOOGLE_TOKEN_JSON.")
        except Exception as e:
            print(f"❌ Error loading GOOGLE_TOKEN_JSON: {e}")

    # 2. Try Base64 encoded pickle (deprecated fallback)
    if not creds:
        token_b64 = os.getenv('GOOGLE_TOKEN_BASE64')
        if token_b64:
            try:
                print("🔑 Attempting to load credentials from GOOGLE_TOKEN_BASE64...")
                creds_data = base64.b64decode(token_b64)
                creds = pickle.loads(creds_data)
                print("✅ Successfully loaded credentials from GOOGLE_TOKEN_BASE64.")
            except Exception as e:
                print(f"❌ Error decoding GOOGLE_TOKEN_BASE64: {e}")

    # 3. Fallback to local file
    if not creds:
        token_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'token.pickle')
        print(f"📁 Checking for local token at: {token_path}")
        if os.path.exists(token_path):
            try:
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
                print("✅ Successfully loaded credentials from local file.")
            except Exception as e:
                print(f"❌ Error loading local token: {e}")
    
    if not creds:
        print("⚠️ No credentials found (env or file)!")
        return None

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print("🔄 Token expired, attempting refresh...")
            try:
                creds.refresh(Request())
                print("✅ Token refreshed successfully.")
            except Exception as e:
                print(f"❌ Error refreshing token: {e}")
                return None
        else:
            print("⚠️ Credentials invalid and cannot be refreshed.")
            return None
            
    return creds

def get_active_goals():
    """Fetch active goals from Google Sheets."""
    print("📋 Starting get_active_goals()...")
    creds = get_credentials()
    if not creds:
        print("❌ get_active_goals: Could not get credentials.")
        return []
        
    try:
        service = build('sheets', 'v4', credentials=creds)
        sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
        print(f"📊 Fetching from Sheet ID: {sheet_id}")
        
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Goals!A:K"
        ).execute()
        
        values = result.get('values', [])
        print(f"📑 Total rows found: {len(values)}")
        
        if len(values) <= 1:
            print("ℹ️ No goal data found beyond header.")
            return []
            
        active_goals = []
        for i, row in enumerate(values[1:], start=2):
            if len(row) < 7:
                continue
            
            status = row[6].strip()
            print(f"🔍 Row {i}: Name='{row[1]}' Status='{status}'")
            
            if status == 'Active':
                goal = {
                    'id': row[0],
                    'name': row[1],
                    'description': row[2] if len(row) > 2 else '',
                    'due_date': row[5] if len(row) > 5 else '',
                    'priority': row[7] if len(row) > 7 else 'Medium',
                    'progress': row[10] if len(row) > 10 else ''
                }
                active_goals.append(goal)
                
        print(f"✅ Found {len(active_goals)} active goals.")
        return active_goals
    except Exception as e:
        print(f"❌ Error in get_active_goals: {e}")
        return []

def get_daily_tasks():
    """Fetch tasks due today or high priority."""
    # For now, just return active goals as a summary
    return get_active_goals()
