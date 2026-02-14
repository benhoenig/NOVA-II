#!/usr/bin/env python3
"""
Update NOVA II Google Sheets schema with new sheets and redesigned structure.

This script:
1. Creates new "Action Plans" sheet
2. Renames and redesigns "Business" to "Business Portfolio"
3. Migrates existing data appropriately

Usage:
    python update_schema.py
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

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
DEFAULT_SHEET_ID = '194ZhTkYYog4qHGALr0qSYuX4iXvuypELRKoVz_--3DA'

def get_credentials():
    """Get or refresh Google API credentials."""
    creds = None
    
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def get_sheet_id_by_name(service, spreadsheet_id, sheet_name):
    """Get sheet ID by name."""
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in spreadsheet.get('sheets', []):
        if sheet['properties']['title'] == sheet_name:
            return sheet['properties']['sheetId']
    return None

def create_action_plans_sheet(service, spreadsheet_id):
    """Create Action Plans sheet with proper schema."""
    print("📋 Creating Action Plans sheet...")
    
    # Check if exists
    sheet_id = get_sheet_id_by_name(service, spreadsheet_id, 'Action Plans')
    
    if not sheet_id:
        # Create sheet
        request = {
            'addSheet': {
                'properties': {
                    'title': 'Action Plans'
                }
            }
        }
        
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [request]}
        ).execute()
        
        sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']
        print("  ✓ Created Action Plans sheet")
    else:
        print("  ✓ Action Plans sheet already exists")
    
    # Set up headers
    headers = [
        'Plan ID', 'Goal ID', 'Goal Name', 'Task Number', 
        'Task Description', 'Timeline', 'Status', 'Due Date',
        'Completed Date', 'Notes'
    ]
    
    body = {'values': [headers]}
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Action Plans!A1:J1",
        valueInputOption='RAW',
        body=body
    ).execute()
    
    # Format headers
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
                        'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.2},
                        'textFormat': {
                            'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0},
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
                    'gridProperties': {'frozenRowCount': 1}
                },
                'fields': 'gridProperties.frozenRowCount'
            }
        }
    ]
    
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': requests}
    ).execute()
    
    print(f"  ✓ Set up headers ({len(headers)} columns)")
    return sheet_id

def backup_business_data(service, spreadsheet_id):
    """Backup existing Business sheet data."""
    print("💾 Backing up Business sheet data...")
    
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="Business!A:Z"
        ).execute()
        
        values = result.get('values', [])
        print(f"  ✓ Backed up {len(values)} rows")
        return values
    except:
        print("  ⚠️  No data to backup")
        return []

def redesign_business_sheet(service, spreadsheet_id, backup_data):
    """Redesign Business sheet to Business Portfolio."""
    print("🏢 Redesigning Business → Business Portfolio...")
    
    sheet_id = get_sheet_id_by_name(service, spreadsheet_id, 'Business')
    
    # Rename sheet
    requests = [{
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheet_id,
                'title': 'Business Portfolio'
            },
            'fields': 'title'
        }
    }]
    
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': requests}
    ).execute()
    
    print("  ✓ Renamed to Business Portfolio")
    
    # Clear existing data
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range="Business Portfolio!A:Z"
    ).execute()
    
    # New headers
    headers = [
        'Business ID', 'Business Name', 'Description', 'Status',
        'Business Model', 'Target Customer', 'Revenue Model', 'Current Stage',
        'Monthly Revenue', 'Customer Count', 'Key Metrics', 'Pain Points',
        'Next Steps', 'Related Goals', 'Notes', 'Started Date', 'Last Updated'
    ]
    
    body = {'values': [headers]}
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Business Portfolio!A1:Q1",
        valueInputOption='RAW',
        body=body
    ).execute()
    
    # Format headers
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
                        'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.2},
                        'textFormat': {
                            'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0},
                            'bold': True
                        }
                    }
                },
                'fields': 'userEnteredFormat(backgroundColor,textFormat)'
            }
        }
    ]
    
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': requests}
    ).execute()
    
    print(f"  ✓ Set up new schema ({len(headers)} columns)")
    return sheet_id

def migrate_data_to_notes(service, spreadsheet_id, backup_data):
    """Migrate old Business data to Notes sheet."""
    if len(backup_data) <= 1:  # Only headers or empty
        print("  ℹ️  No data to migrate")
        return
    
    print("📝 Migrating old Business data to Notes...")
    
    # Skip header, process data rows
    for i, row in enumerate(backup_data[1:], start=1):
        if not row or len(row) < 2:
            continue
        
        # Old schema: Entry ID, Topic, Content, Category, Related To, Tags, Created Date, Last Modified
        old_id = row[0] if len(row) > 0 else ''
        topic = row[1] if len(row) > 1 else ''
        content = row[2] if len(row) > 2 else ''
        category = row[3] if len(row) > 3 else ''
        tags = row[5] if len(row) > 5 else ''
        created = row[6] if len(row) > 6 else ''
        
        # New Notes schema: Note ID, Title, Content, Category, Tags, Created Date, Last Modified, Source/Reference
        note_id = f"NOTE-{i:03d}"  # Generate new ID
        
        # Append to Notes
        note_row = [note_id, topic, content, category, tags, created, created, f"Migrated from {old_id}"]
        
        body = {'values': [note_row]}
        
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range="Notes!A:Z",
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
    
    print(f"  ✓ Migrated {len(backup_data)-1} entries to Notes")

def main():
    """Main function to update schema."""
    print("🚀 Updating NOVA II Schema...\n")
    
    # Get credentials
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    # Get Sheet ID
    sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
    print(f"📋 Target Sheet ID: {sheet_id}\n")
    
    # 1. Create Action Plans sheet
    create_action_plans_sheet(service, sheet_id)
    print()
    
    # 2. Backup Business data
    backup_data = backup_business_data(service, sheet_id)
    print()
    
    # 3. Redesign Business sheet
    redesign_business_sheet(service, sheet_id, backup_data)
    print()
    
    # 4. Migrate old data to Notes
    migrate_data_to_notes(service, sheet_id, backup_data)
    print()
    
    print("✅ Schema update complete!")
    print(f"\n🔗 View your sheet: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
