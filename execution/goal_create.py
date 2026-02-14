#!/usr/bin/env python3
"""
Create new goals in NOVA II Google Sheets.

This script creates goals with interactive prompting for missing details.

Usage:
    python goal_create.py <name> [OPTIONS]
    
Options:
    --description, -d    Goal description
    --due, -D            Due date (YYYY-MM-DD)
    --type, -t           Goal type/category
    --priority, -p       Priority (High/Medium/Low)
    --reminder, -r       Reminder schedule (e.g., "Daily 9AM", "Every 3 days")
    
Examples:
    python goal_create.py "Create TikTok content" -d "AI automation topic" -D "2026-02-21" -r "Daily 9AM"
    python goal_create.py "Launch product" --priority High --due "2026-03-01"
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

# Add module path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from llm_utils import LLMClient
    from action_plan_create import create_action_plan
except ImportError:
    pass

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

def generate_goal_id(service, spreadsheet_id):
    """Generate unique Goal ID."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="Goals!A:A"
        ).execute()
        
        values = result.get('values', [])
        count = len(values)  # Includes header
        next_id = f"GOAL-{count:03d}"
        
        return next_id
    except:
        return "GOAL-001"

def parse_due_date(date_str):
    """
    Parse due date string into YYYY-MM-DD format.
    
    Handles various formats like:
    - 2026-02-21
    - วันศุกร์หน้า (next Friday - needs context)
    - ภายในสัปดาห์นี้ (this week)
    """
    if not date_str:
        return None
    
    # Already in YYYY-MM-DD format
    if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
        return date_str
    
    # Thai relative dates - simplified heuristics
    date_str_lower = date_str.lower()
    
    if 'วันนี้' in date_str_lower or 'today' in date_str_lower:
        return datetime.now().strftime('%Y-%m-%d')
    
    if 'พรุ่งนี้' in date_str_lower or 'tomorrow' in date_str_lower:
        return (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    if 'สัปดาห์' in date_str_lower or 'week' in date_str_lower:
        # Default to end of week (Sunday)
        days_until_sunday = 6 - datetime.now().weekday()
        if days_until_sunday < 0:
            days_until_sunday += 7
        return (datetime.now() + timedelta(days=days_until_sunday)).strftime('%Y-%m-%d')
    
    if 'เดือน' in date_str_lower or 'month' in date_str_lower:
        # End of month
        next_month = datetime.now().replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        return last_day.strftime('%Y-%m-%d')
    
    # If can't parse, return as-is and let user clarify
    return date_str

def generate_breakdown(name, description, due_date):
    """Generate sub-tasks using LLM."""
    try:
        client = LLMClient()
        prompt = f"""
        I have a goal: "{name}"
        Description: {description}
        Due Date: {due_date}
        Current Date: {datetime.now().strftime('%Y-%m-%d')}
        
        Please break this goal down into 3-7 concrete, actionable sub-tasks.
        Return a JSON object with a key 'tasks' containing a list of strings.
        Each string should be in the format "Timeline: Task Description".
        
        Examples:
        - "Day 1: Research competitors"
        - "Week 1: Build prototype"
        - "Feb 20: Submit report"
        
        Make the timeline realistic based on the due date.
        """
        
        response = client.generate_json(prompt)
        if response and 'tasks' in response:
            return response['tasks']
            
    except Exception as e:
        print(f"Warning: Failed to generate breakdown: {e}")
    
    return []

def create_goal(name, description='', due_date=None, goal_type='', priority='Medium', reminder='', auto_breakdown=False):
    """
    Create a new goal in Google Sheets.
    
    Args:
        name: Goal name (required)
        description: Detailed description
        due_date: Due date (YYYY-MM-DD)
        goal_type: Type/category
        priority: High/Medium/Low
        reminder: Reminder schedule
        
    Returns:
        Dict with success status and goal details
    """
    print(f"🎯 Creating goal: {name}\n")
    
    # Get credentials and create service
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    # Get Sheet ID
    sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
    
    # Generate Goal ID
    goal_id = generate_goal_id(service, sheet_id)
    
    # Timestamps
    created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    start_date = datetime.now().strftime('%Y-%m-%d')
    
    # Parse due date
    parsed_due = parse_due_date(due_date) if due_date else ''
    
    # Goals sheet columns:
    # Goal ID, Goal Name, Description, Type/Category, Start Date, Due Date, 
    # Status, Priority, Reminder Schedule, Last Reminded, Progress Notes, 
    # Created Date, Completed Date
    
    row_data = [
        goal_id,           # Goal ID
        name,              # Goal Name
        description,       # Description
        goal_type,         # Type/Category
        start_date,        # Start Date
        parsed_due,        # Due Date
        'Active',          # Status
        priority,          # Priority
        reminder,          # Reminder Schedule
        '',                # Last Reminded
        '',                # Progress Notes
        created,           # Created Date
        ''                 # Completed Date
    ]
    
    # Append to Goals sheet
    try:
        range_name = "Goals!A:Z"
        body = {
            'values': [row_data]
        }
        
        result = service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=range_name,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        print(f"✅ Goal created successfully!\n")
        print(f"{'='*50}")
        print(f"📌 {name}")
        print(f"{'='*50}")
        print(f"ID: {goal_id}")
        print(f"Description: {description or '(none)'}")
        print(f"Due Date: {parsed_due or '(not set)'}")
        print(f"Priority: {priority}")
        print(f"Status: Active")
        if reminder:
            print(f"Reminder: {reminder}")
        print(f"Created: {created}")
        print()
        
        # Calculate days until due
        if parsed_due:
            try:
                due_dt = datetime.strptime(parsed_due, '%Y-%m-%d')
                days_left = (due_dt - datetime.now()).days
                if days_left >= 0:
                    print(f"⏰ {days_left} day(s) remaining")
                else:
                    print(f"⚠️  Overdue by {abs(days_left)} day(s)")
            except:
                pass
        
        # Auto-breakdown
        if auto_breakdown:
            print(f"🧠 Generating action plan with AI...")
            tasks = generate_breakdown(name, description, parsed_due)
            
            if tasks:
                print(f"  Found {len(tasks)} suggested tasks.")
                create_action_plan(goal_id, name, tasks, parsed_due)
            else:
                print(f"  Could not generate tasks automatically.")
        
        return {
            'success': True,
            'goal_id': goal_id,
            'name': name,
            'due_date': parsed_due,
            'status': 'Active'
        }
        
    except HttpError as error:
        print(f"❌ Error creating goal: {error}")
        return {'success': False, 'error': str(error)}

def main():
    """Main function to parse arguments and create goal."""
    parser = argparse.ArgumentParser(
        description='Create new goal in NOVA II'
    )
    
    parser.add_argument('name', help='Goal name')
    parser.add_argument('--description', '-d', default='', help='Goal description')
    parser.add_argument('--due', '-D', help='Due date (YYYY-MM-DD or natural language)')
    parser.add_argument('--type', '-t', default='', help='Goal type/category')
    parser.add_argument('--priority', '-p', default='Medium', choices=['High', 'Medium', 'Low'], help='Priority level')
    parser.add_argument('--reminder', '-r', default='', help='Reminder schedule')
    parser.add_argument('--auto-breakdown', '-a', action='store_true', help='Automatically break down into tasks using AI')
    
    args = parser.parse_args()
    
    result = create_goal(
        name=args.name,
        description=args.description,
        due_date=args.due,
        goal_type=args.type,
        priority=args.priority,
        reminder=args.reminder,
        auto_breakdown=args.auto_breakdown
    )
    
    return 0 if result['success'] else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Goal creation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
