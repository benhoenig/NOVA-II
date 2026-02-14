#!/usr/bin/env python3
"""
Update goals in NOVA II Google Sheets.

This script updates goal status, progress notes, and other fields.

Usage:
    python goal_update.py <goal_identifier> [OPTIONS]
    
Options:
    --status, -s      Update status (Active/Completed/Paused/Cancelled)
    --notes, -n       Add progress notes
    --priority, -p    Update priority (High/Medium/Low)
    --due, -d         Update due date (YYYY-MM-DD)
    --reminder, -r    Update reminder schedule
    
Examples:
    python goal_update.py "GOAL-001" --status Completed
    python goal_update.py "Create TikTok" --notes "Recorded first video"
    python goal_update.py "GOAL-002" --priority High --due "2026-02-25"
"""

import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

# Load environment variables
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
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json not found!")
                print("Please run setup first. See GOOGLE_SETUP.md")
                sys.exit(1)
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def find_goal(service, spreadsheet_id, identifier):
    """
    Find a goal by ID or name.
    
    Returns:
        Tuple of (row_number, goal_data) or (None, None) if not found
    """
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="Goals!A:M"
        ).execute()
        
        values = result.get('values', [])
        
        if len(values) <= 1:
            return None, None
        
        headers = values[0]
        
        # Search by ID or name
        for i, row in enumerate(values[1:], start=2):
            if not row:
                continue
            
            # Check if identifier matches Goal ID or Goal Name
            goal_id = row[0] if len(row) > 0 else ''
            goal_name = row[1] if len(row) > 1 else ''
            
            if identifier == goal_id or identifier.lower() in goal_name.lower():
                # Create dict of goal data
                goal_data = {}
                for j, header in enumerate(headers):
                    if j < len(row):
                        goal_data[header] = row[j]
                    else:
                        goal_data[header] = ''
                
                return i, goal_data
        
        return None, None
        
    except HttpError as error:
        print(f"Error finding goal: {error}")
        return None, None

def update_goal(identifier, status=None, notes=None, priority=None, due_date=None, reminder=None):
    """
    Update a goal in Google Sheets.
    
    Args:
        identifier: Goal ID or name to search for
        status: New status
        notes: Progress notes to add
        priority: New priority
        due_date: New due date
        reminder: New reminder schedule
        
    Returns:
        Dict with success status
    """
    print(f"🔄 Updating goal: {identifier}\n")
    
    # Get credentials and create service
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    # Get Sheet ID
    sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
    
    # Find the goal
    row_num, goal_data = find_goal(service, sheet_id, identifier)
    
    if not goal_data:
        print(f"❌ Goal not found: {identifier}")
        print("Tip: Use Goal ID (e.g., GOAL-001) or part of the goal name")
        return {'success': False, 'error': 'Goal not found'}
    
    print(f"Found: {goal_data.get('Goal Name', '')}\n")
    
    # Prepare updates
    # Column mapping: A=ID, B=Name, C=Desc, D=Type, E=Start, F=Due, G=Status, H=Priority, I=Reminder, J=LastReminded, K=Notes, L=Created, M=Completed
    updates = []
    
    if status:
        # Update Status (column G)
        updates.append({
            'range': f"Goals!G{row_num}",
            'values': [[status]]
        })
        
        # If marking as Completed, set Completed Date (column M)
        if status == 'Completed':
            completed_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            updates.append({
                'range': f"Goals!M{row_num}",
                'values': [[completed_date]]
            })
    
    if priority:
        # Update Priority (column H)
        updates.append({
            'range': f"Goals!H{row_num}",
            'values': [[priority]]
        })
    
    if due_date:
        # Update Due Date (column F)
        updates.append({
            'range': f"Goals!F{row_num}",
            'values': [[due_date]]
        })
    
    if reminder:
        # Update Reminder Schedule (column I)
        updates.append({
            'range': f"Goals!I{row_num}",
            'values': [[reminder]]
        })
    
    if notes:
        # Append to Progress Notes (column K)
        existing_notes = goal_data.get('Progress Notes', '')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        new_note = f"[{timestamp}] {notes}"
        
        if existing_notes:
            updated_notes = f"{existing_notes}\n{new_note}"
        else:
            updated_notes = new_note
        
        updates.append({
            'range': f"Goals!K{row_num}",
            'values': [[updated_notes]]
        })
    
    if not updates:
        print("⚠️  No updates specified")
        return {'success': False, 'error': 'No updates specified'}
    
    # Apply updates
    try:
        body = {
            'valueInputOption': 'RAW',
            'data': updates
        }
        
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body=body
        ).execute()
        
        print("✅ Goal updated successfully!\n")
        print(f"{'='*50}")
        print(f"📌 {goal_data.get('Goal Name', '')}")
        print(f"{'='*50}")
        
        if status:
            print(f"Status: {goal_data.get('Status', '')} → {status}")
        if priority:
            print(f"Priority: {goal_data.get('Priority', '')} → {priority}")
        if due_date:
            print(f"Due Date: {goal_data.get('Due Date', '')} → {due_date}")
        if reminder:
            print(f"Reminder: {reminder}")
        if notes:
            print(f"Added Note: {notes}")
        
        return {
            'success': True,
            'goal_id': goal_data.get('Goal ID', ''),
            'name': goal_data.get('Goal Name', '')
        }
        
    except HttpError as error:
        print(f"❌ Error updating goal: {error}")
        return {'success': False, 'error': str(error)}

def main():
    """Main function to parse arguments and update goal."""
    parser = argparse.ArgumentParser(
        description='Update goal in NOVA II'
    )
    
    parser.add_argument('identifier', help='Goal ID or name')
    parser.add_argument('--status', '-s', choices=['Active', 'Completed', 'Paused', 'Cancelled'], help='Update status')
    parser.add_argument('--notes', '-n', help='Add progress notes')
    parser.add_argument('--priority', '-p', choices=['High', 'Medium', 'Low'], help='Update priority')
    parser.add_argument('--due', '-d', help='Update due date (YYYY-MM-DD)')
    parser.add_argument('--reminder', '-r', help='Update reminder schedule')
    
    args = parser.parse_args()
    
    result = update_goal(
        identifier=args.identifier,
        status=args.status,
        notes=args.notes,
        priority=args.priority,
        due_date=args.due,
        reminder=args.reminder
    )
    
    return 0 if result['success'] else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Update cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
