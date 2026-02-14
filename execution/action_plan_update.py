#!/usr/bin/env python3
"""
Update action plan task status in NOVA II.

Usage:
    python action_plan_update.py <plan_id> <task_number> --status <status> [--notes "notes"]
    
Example:
    python action_plan_update.py "PLAN-001" 1 --status "Completed"
    python action_plan_update.py "PLAN-001" 2 --status "In Progress" --notes "Started testing"
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

def find_task(service, spreadsheet_id, plan_id, task_number):
    """Find task row number by Plan ID and Task Number."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="Action Plans!A:J"
        ).execute()
        
        values = result.get('values', [])
        
        if len(values) <= 1:
            return None, None
        
        headers = values[0]
        
        # Find matching task
        for i, row in enumerate(values[1:], start=2):
            if len(row) < 4:
                continue
            
            row_plan_id = row[0]  # Plan ID
            row_task_num = row[3]  # Task Number
            
            if row_plan_id == plan_id and str(row_task_num) == str(task_number):
                # Create task dict
                task_data = {}
                for j, header in enumerate(headers):
                    if j < len(row):
                        task_data[header] = row[j]
                    else:
                        task_data[header] = ''
                
                return i, task_data
        
        return None, None
        
    except HttpError as error:
        print(f"Error finding task: {error}")
        return None, None

def update_task(plan_id, task_number, status=None, notes=None):
    """
    Update action plan task.
    
    Args:
        plan_id: Plan ID
        task_number: Task number
        status: New status (Not Started, In Progress, Completed)
        notes: Additional notes
        
    Returns:
        Dict with success status
    """
    print(f"🔄 Updating task {task_number} in {plan_id}...\n")
    
    # Get credentials
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    # Get Sheet ID
    sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
    
    # Find task
    row_num, task_data = find_task(service, sheet_id, plan_id, task_number)
    
    if not task_data:
        print(f"❌ Task not found: {plan_id} Task #{task_number}")
        return {'success': False, 'error': 'Task not found'}
    
    print(f"Found: {task_data.get('Task Description', '')}\n")
    
    # Prepare updates
    updates = []
    
    if status:
        # Update Status (column G)
        updates.append({
            'range': f"Action Plans!G{row_num}",
            'values': [[status]]
        })
        
        # If marking as completed, set Completed Date (column I)
        if status == 'Completed':
            completed_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            updates.append({
                'range': f"Action Plans!I{row_num}",
                'values': [[completed_date]]
            })
    
    if notes:
        # Update Notes (column J)
        existing_notes = task_data.get('Notes', '')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        new_note = f"[{timestamp}] {notes}"
        
        if existing_notes:
            updated_notes = f"{existing_notes}\n{new_note}"
        else:
            updated_notes = new_note
        
        updates.append({
            'range': f"Action Plans!J{row_num}",
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
        
        print("✅ Task updated successfully!\n")
        print(f"{'='*60}")
        print(f"Task #{task_number}: {task_data.get('Task Description', '')}")
        print(f"{'='*60}")
        
        if status:
            print(f"Status: {task_data.get('Status', '')} → {status}")
        if notes:
            print(f"Added Note: {notes}")
        
        return {
            'success': True,
            'plan_id': plan_id,
            'task_number': task_number
        }
        
    except HttpError as error:
        print(f"❌ Error updating task: {error}")
        return {'success': False, 'error': str(error)}

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Update action plan task'
    )
    
    parser.add_argument('plan_id', help='Plan ID (e.g., PLAN-001)')
    parser.add_argument('task_number', type=int, help='Task number')
    parser.add_argument('--status', '-s', 
                       choices=['Not Started', 'In Progress', 'Completed'],
                       help='Update status')
    parser.add_argument('--notes', '-n', help='Add notes')
    
    args = parser.parse_args()
    
    result = update_task(
        plan_id=args.plan_id,
        task_number=args.task_number,
        status=args.status,
        notes=args.notes
    )
    
    return 0 if result['success'] else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
