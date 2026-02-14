import os
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
DEFAULT_SHEET_ID = '194ZhTkYYog4qHGALr0qSYuX4iXvuypELRKoVz_--3DA'

def get_credentials():
    """Get or refresh Google API credentials."""
    creds = None
    # Look for token.pickle in project root
    token_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'token.pickle')
    
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Note: In a deployed env, we expect token.pickle to exist
            return None
            
    return creds

def get_active_goals():
    """Fetch active goals from Google Sheets."""
    creds = get_credentials()
    if not creds:
        return []
        
    service = build('sheets', 'v4', credentials=creds)
    sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
    
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Goals!A:K"
        ).execute()
        
        values = result.get('values', [])
        if len(values) <= 1:
            return []
            
        headers = values[0]
        active_goals = []
        
        for row in values[1:]:
            if len(row) < 7: continue
            
            status = row[6]
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
                
        return active_goals
    except Exception as e:
        print(f"Error fetching goals: {e}")
        return []

def get_daily_tasks():
    """Fetch tasks due today or high priority."""
    # For now, just return active goals as a summary
    return get_active_goals()
