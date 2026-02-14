#!/usr/bin/env python3
"""
Check and generate goal reminders for NOVA II.

This script checks active goals that need reminders based on their
reminder schedule and last reminded time.

Usage:
    python goal_reminders.py [--update]
    
Options:
    --update    Update "Last Reminded" timestamp after generating reminders
    
Examples:
    python goal_reminders.py              # Just check and display
    python goal_reminders.py --update     # Check, display, and update timestamps
"""

import os
import sys
import argparse
import json
import re
import pickle
import base64
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# SCOPES: Add Gmail Send scope
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.send'
]
DEFAULT_SHEET_ID = '194ZhTkYYog4qHGALr0qSYuX4iXvuypELRKoVz_--3DA'
USER_ID_FILE = 'user_ids.json'

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

def send_email_via_api(service, to_email, subject, message_text):
    """Send email using Gmail API."""
    try:
        message = MIMEText(message_text)
        message['to'] = to_email
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        body = {'raw': raw_message}
        
        message = service.users().messages().send(userId='me', body=body).execute()
        print(f"📧 Email sent to {to_email} (Msg ID: {message['id']})")
        return message
    except HttpError as error:
        print(f"❌ An error occurred sending email: {error}")
        return None

def parse_reminder_schedule(schedule_str):
    """
    Parse reminder schedule string into hours interval.
    
    Examples:
        "Daily 9AM" -> check if 9AM passed today
        "Every 3 days" -> check if 3 days since last reminder
        "Weekly Monday" -> check if Monday and 7+ days
    
    Returns:
        hours_interval or None if can't parse
    """
    if not schedule_str:
        return None
    
    schedule_lower = schedule_str.lower()
    
    # Daily patterns
    if 'daily' in schedule_lower or 'ทุกวัน' in schedule_lower:
        return 24  # Check every 24 hours
    
    # Weekly patterns
    if 'weekly' in schedule_lower or 'สัปดาห์' in schedule_lower:
        return 168  # 7 days in hours
    
    # "Every X days/hours" patterns
    match = re.search(r'every\s+(\d+)\s+(day|hour|วัน|ชั่วโมง)', schedule_lower)
    if match:
        number = int(match.group(1))
        unit = match.group(2)
        if 'hour' in unit or 'ชั่วโมง' in unit:
            return number
        else:  # days
            return number * 24
    
    # Default to daily if has any schedule
    return 24

def should_remind(last_reminded_str, reminder_schedule):
    """
    Determine if a reminder should be sent now.
    
    Args:
        last_reminded_str: Last reminded timestamp (YYYY-MM-DD HH:MM:SS) or empty
        reminder_schedule: Reminder schedule string
        
    Returns:
        Boolean indicating if reminder is due
    """
    if not reminder_schedule:
        return False
    
    hours_interval = parse_reminder_schedule(reminder_schedule)
    if not hours_interval:
        return False
    
    # If never reminded, send reminder
    if not last_reminded_str:
        return True
    
    try:
        last_reminded = datetime.strptime(last_reminded_str, '%Y-%m-%d %H:%M:%S')
        time_since = datetime.now() - last_reminded
        hours_since = time_since.total_seconds() / 3600
        
        return hours_since >= hours_interval
        
    except:
        # If can't parse, assume should remind
        return True

def check_reminders(update_timestamps=False):
    """
    Check all active goals and generate reminders.
    """
    print("⏰ Checking goal reminders...\n")
    
    # Get credentials (covers both Sheets and Gmail)
    creds = get_credentials()
    sheets_service = build('sheets', 'v4', credentials=creds)
    gmail_service = build('gmail', 'v1', credentials=creds)
    
    # Get Sheet ID
    sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
    
    # Get all goals
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Goals!A:M"
        ).execute()
        
        values = result.get('values', [])
        
        if len(values) <= 1:
            print("No goals found")
            return []
        
        headers = values[0]
        reminders = []
        updates = []
        
        # Check each goal
        for i, row in enumerate(values[1:], start=2):
            if not row or len(row) < 9:
                continue
            
            # Parse goal data
            goal_id = row[0] if len(row) > 0 else ''
            goal_name = row[1] if len(row) > 1 else ''
            description = row[2] if len(row) > 2 else ''
            goal_type = row[3] if len(row) > 3 else ''
            due_date = row[5] if len(row) > 5 else ''
            status = row[6] if len(row) > 6 else ''
            priority = row[7] if len(row) > 7 else ''
            reminder_schedule = row[8] if len(row) > 8 else ''
            last_reminded = row[9] if len(row) > 9 else ''
            progress_notes = row[10] if len(row) > 10 else ''
            
            # Only check Active goals with reminder schedule
            if status != 'Active':
                continue
            
            if not reminder_schedule:
                continue
            
            # Check if reminder is due
            if should_remind(last_reminded, reminder_schedule):
                # Calculate days until due
                days_left = None
                if due_date:
                    try:
                        due_dt = datetime.strptime(due_date, '%Y-%m-%d')
                        days_left = (due_dt - datetime.now()).days
                    except:
                        pass
                
                reminder_data = {
                    'row_number': i,
                    'goal_id': goal_id,
                    'name': goal_name,
                    'description': description,
                    'type': goal_type,
                    'due_date': due_date,
                    'days_left': days_left,
                    'priority': priority,
                    'progress_notes': progress_notes,
                    'reminder_schedule': reminder_schedule
                }
                
                reminders.append(reminder_data)
                
                # Prepare timestamp update
                if update_timestamps:
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    updates.append({
                        'range': f"Goals!J{i}",  # Column J = Last Reminded
                        'values': [[now]]
                    })
        
        # Update timestamps if requested
        if updates and update_timestamps:
            try:
                body = {
                    'valueInputOption': 'RAW',
                    'data': updates
                }
                
                sheets_service.spreadsheets().values().batchUpdate(
                    spreadsheetId=sheet_id,
                    body=body
                ).execute()
                
                print(f"✓ Updated {len(updates)} reminder timestamp(s)\n")
            except HttpError as error:
                print(f"Warning: Could not update timestamps: {error}\n")
        
        # Display reminders
        if not reminders:
            print("✅ No reminders due at this time")
            return []
        
        print(f"🔔 {len(reminders)} Reminder(s):\n")
        
        # Construct Email Message
        email_body = f"🔔 NOVA II Reminders ({len(reminders)})\n"
        email_body += "="*60 + "\n"
        
        for i, reminder in enumerate(reminders, 1):
            print(f"\n📌 Reminder #{i}")
            print(f"{'='*60}")
            print(f"Goal: {reminder['name']}")
            
            # Add to email msg
            email_body += f"\n📌 {reminder['name']}\n"
            
            if reminder['description']:
                print(f"Description: {reminder['description']}")
                email_body += f"   Description: {reminder['description']}\n"
            
            if reminder['due_date']:
                print(f"Due: {reminder['due_date']}", end='')
                email_body += f"   Due: {reminder['due_date']}"
                if reminder['days_left'] is not None:
                    if reminder['days_left'] >= 0:
                        print(f" ({reminder['days_left']} day(s) remaining)")
                        email_body += f" ({reminder['days_left']}d left)\n"
                    else:
                        print(f" (⚠️  OVERDUE by {abs(reminder['days_left'])} days)")
                        email_body += f" (⚠️ OVERDUE {abs(reminder['days_left'])}d)\n"
                else:
                    print()
                    email_body += "\n"
            
            print(f"Priority: {reminder['priority']}")
            # Show latest progress note if any
            if reminder['progress_notes']:
                notes_lines = reminder['progress_notes'].split('\n')
                latest_note = notes_lines[-1] if notes_lines else ''
                if latest_note:
                    print(f"Latest: {latest_note}")
                    email_body += f"   Latest Note: {latest_note}\n"
            
            print(f"{'='*60}")
            email_body += "-"*30 + "\n"

        # Send Email via Gmail API
        try:
            user_email = os.getenv('GMAIL_USER')
            
            if user_email:
                send_email_via_api(
                    gmail_service, 
                    user_email, 
                    f"NOVA II Daily Briefing - {datetime.now().strftime('%Y-%m-%d')}",
                    email_body
                )
            else:
                print("⚠️  GMAIL_USER not set in .env. Skipping email.")
                
        except Exception as e:
             print(f"❌ Error sending email: {e}")

        return reminders
        
    except HttpError as error:
        print(f"❌ Error checking reminders: {error}")
        return []

def main():
    """Main function to check reminders."""
    parser = argparse.ArgumentParser(
        description='Check goal reminders in NOVA II'
    )
    
    parser.add_argument('--update', action='store_true', help='Update Last Reminded timestamps')
    
    args = parser.parse_args()
    
    reminders = check_reminders(update_timestamps=args.update)
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Reminder check cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
