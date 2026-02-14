#!/usr/bin/env python3
"""
Initialize NOVA II Google Sheets with proper schema.

This script sets up the Google Sheet with 6 sheets and their column headers:
- Goals (เป้าหมาย)
- Knowledge - Notes (บันทึก)
- Knowledge - Lessons Learned (บทเรียน)
- Knowledge - Business (ธุรกิจ)
- Knowledge - Customers/Contacts (ลูกค้า/ผู้ติดต่อ)
- Knowledge - Other (อื่นๆ)

Usage:
    python initialize_sheets.py

Environment Variables Required:
    GOOGLE_SHEET_ID - The ID of the Google Sheet (from URL)
"""

import os
import sys
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

# Load environment variables
load_dotenv()

# Google Sheets API scope
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Default Google Sheet ID (can be overridden by env var)
DEFAULT_SHEET_ID = '194ZhTkYYog4qHGALr0qSYuX4iXvuypELRKoVz_--3DA'

def get_credentials():
    """
    Get or refresh Google API credentials.
    
    Returns:
        Credentials object for Google Sheets API
    """
    creds = None
    
    # Token file stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json not found!")
                print("\nPlease follow these steps:")
                print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
                print("2. Create a new project or select existing one")
                print("3. Enable Google Sheets API")
                print("4. Create OAuth 2.0 credentials (Desktop app)")
                print("5. Download credentials.json to this directory")
                sys.exit(1)
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def create_sheet_if_not_exists(service, spreadsheet_id, sheet_name):
    """
    Create a sheet in the spreadsheet if it doesn't already exist.
    
    Args:
        service: Google Sheets API service object
        spreadsheet_id: ID of the spreadsheet
        sheet_name: Name of the sheet to create
        
    Returns:
        Sheet ID of the created or existing sheet
    """
    try:
        # Get existing sheets
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        
        # Check if sheet already exists
        for sheet in sheets:
            if sheet['properties']['title'] == sheet_name:
                print(f"  ✓ Sheet '{sheet_name}' already exists")
                return sheet['properties']['sheetId']
        
        # Create new sheet
        request = {
            'addSheet': {
                'properties': {
                    'title': sheet_name
                }
            }
        }
        
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [request]}
        ).execute()
        
        sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
        print(f"  ✓ Created sheet '{sheet_name}'")
        return sheet_id
        
    except HttpError as error:
        print(f"  ✗ Error with sheet '{sheet_name}': {error}")
        raise

def setup_sheet_headers(service, spreadsheet_id, sheet_name, headers):
    """
    Set up column headers for a sheet with formatting.
    
    Args:
        service: Google Sheets API service object
        spreadsheet_id: ID of the spreadsheet
        sheet_name: Name of the sheet
        headers: List of column header names
    """
    try:
        # Write headers
        range_name = f"{sheet_name}!A1:{chr(65 + len(headers) - 1)}1"
        body = {
            'values': [headers]
        }
        
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        # Format headers (bold, background color)
        sheet_id = get_sheet_id(service, spreadsheet_id, sheet_name)
        requests = [
            {
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 0,
                        'endRowIndex': 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': len(headers)
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': {
                                'red': 0.2,
                                'green': 0.2,
                                'blue': 0.2
                            },
                            'textFormat': {
                                'foregroundColor': {
                                    'red': 1.0,
                                    'green': 1.0,
                                    'blue': 1.0
                                },
                                'bold': True
                            }
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                }
            },
            {
                'updateSheetProperties': {
                    'properties': {
                        'sheetId': sheet_id,
                        'gridProperties': {
                            'frozenRowCount': 1
                        }
                    },
                    'fields': 'gridProperties.frozenRowCount'
                }
            }
        ]
        
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': requests}
        ).execute()
        
        print(f"  ✓ Set up headers for '{sheet_name}' ({len(headers)} columns)")
        
    except HttpError as error:
        print(f"  ✗ Error setting headers for '{sheet_name}': {error}")
        raise

def get_sheet_id(service, spreadsheet_id, sheet_name):
    """Get the sheet ID for a given sheet name."""
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in spreadsheet.get('sheets', []):
        if sheet['properties']['title'] == sheet_name:
            return sheet['properties']['sheetId']
    return None

def initialize_nova_sheets():
    """
    Main function to initialize all NOVA II sheets with proper schema.
    """
    print("🚀 Initializing NOVA II Google Sheets...\n")
    
    # Get Sheet ID from environment or use default
    sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
    print(f"📋 Target Sheet ID: {sheet_id}\n")
    
    # Authenticate
    print("🔐 Authenticating with Google...")
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    print("  ✓ Authentication successful\n")
    
    # Define schema for each sheet
    sheets_schema = {
        'Goals': [
            'Goal ID', 'Goal Name', 'Description', 'Type/Category',
            'Start Date', 'Due Date', 'Status', 'Priority',
            'Reminder Schedule', 'Last Reminded', 'Progress Notes',
            'Created Date', 'Completed Date'
        ],
        'Notes': [
            'Note ID', 'Title', 'Content', 'Category', 'Tags',
            'Created Date', 'Last Modified', 'Source/Reference'
        ],
        'Lessons Learned': [
            'Lesson ID', 'Title', 'What Happened', 'What I Learned',
            'How to Apply', 'Category', 'Date', 'Created Date'
        ],
        'Business': [
            'Entry ID', 'Topic', 'Content', 'Category', 'Related To',
            'Tags', 'Created Date', 'Last Modified'
        ],
        'Customers': [
            'Contact ID', 'Name', 'Type', 'Company', 'Contact Info',
            'Notes', 'Last Contact', 'Tags', 'Created Date'
        ],
        'Other': [
            'Entry ID', 'Title', 'Content', 'Category', 'Tags',
            'Created Date', 'Last Modified'
        ]
    }
    
    # Create and set up each sheet
    print("📊 Setting up sheets...\n")
    for sheet_name, headers in sheets_schema.items():
        print(f"Setting up: {sheet_name}")
        create_sheet_if_not_exists(service, sheet_id, sheet_name)
        setup_sheet_headers(service, sheet_id, sheet_name, headers)
        print()
    
    # Remove default "Sheet1" if it exists and is empty
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        
        for sheet in sheets:
            if sheet['properties']['title'] == 'Sheet1':
                sheet_id_to_delete = sheet['properties']['sheetId']
                request = {
                    'deleteSheet': {
                        'sheetId': sheet_id_to_delete
                    }
                }
                service.spreadsheets().batchUpdate(
                    spreadsheetId=sheet_id,
                    body={'requests': [request]}
                ).execute()
                print("🗑️  Removed default 'Sheet1'\n")
                break
    except Exception as e:
        # Ignore if we can't delete Sheet1 (might not exist or might have data)
        pass
    
    print("✅ NOVA II sheets initialized successfully!")
    print(f"\n🔗 View your sheet: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(initialize_nova_sheets())
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
