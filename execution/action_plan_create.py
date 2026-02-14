#!/usr/bin/env python3
"""
Create action plan tasks for a goal in NOVA II.

This script creates actionable sub-tasks for a goal and stores them
in the Action Plans sheet.

Usage:
   python action_plan_create.py <goal_id> <goal_name> --tasks "task1;task2;task3"
    
Example:
    python action_plan_create.py "GOAL-001" "Product Discovery" \
      --tasks "Day 1-2: Test workflow;Day 3-4: Interview customers;Day 5: Analyze results"
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
except ImportError:
    pass

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

def generate_plan_id(service, spreadsheet_id):
    """Generate unique Plan ID."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="Action Plans!A:A"
        ).execute()
        
        values = result.get('values', [])
        count = len(values)
        next_id = f"PLAN-{count:03d}"
        
        return next_id
    except:
        return "PLAN-001"

def generate_tasks_from_context(goal_name, context, due_date=None):
    """Generate tasks using LLM."""
    try:
        client = LLMClient()
        prompt = f"""
        Goal: "{goal_name}"
        Context/Description: {context}
        Due Date: {due_date or 'Not specified'}
        
        Create a list of 3-7 actionable sub-tasks for this goal.
        Return a JSON object with a key 'tasks' containing a list of strings.
        Format: "Timeline: Task Description"
        """
        response = client.generate_json(prompt)
        if response and 'tasks' in response:
            return response['tasks']
    except Exception as e:
        print(f"Warning: Failed to generate tasks: {e}")
    return []

def create_action_plan(goal_id, goal_name, tasks_list, goal_due_date=None):
    """
    Create action plan tasks for a goal.
    
    Args:
        goal_id: Goal ID (e.g., GOAL-001)
        goal_name: Goal name
        tasks_list: List of task strings (format: "Timeline: Description")
        goal_due_date: Optional goal due date for calculating task dates
        
    Returns:
        Dict with success status and plan details
    """
    print(f"📋 Creating action plan for {goal_id}...\n")
    
    # Get credentials
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    # Get Sheet ID
    sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
    
    # Generate Plan ID
    plan_id = generate_plan_id(service, sheet_id)
    
    # Prepare task rows
    rows = []
    
    for i, task in enumerate(tasks_list, start=1):
        # Parse task (format: "Day 1-2: Do something" or just "Do something")
        if ':' in task:
            timeline, description = task.split(':', 1)
            timeline = timeline.strip()
            description = description.strip()
        else:
            timeline = f"Task {i}"
            description = task.strip()
        
        # Action Plans schema:
        # Plan ID, Goal ID, Goal Name, Task Number, Task Description, 
        # Timeline, Status, Due Date, Completed Date, Notes
        
        row = [
            plan_id,           # Plan ID
            goal_id,           # Goal ID
            goal_name,         # Goal Name
            str(i),            # Task Number
            description,       # Task Description
            timeline,          # Timeline
            'Not Started',     # Status
            '',                # Due Date (calculate from timeline if needed)
            '',                # Completed Date
            ''                 # Notes
        ]
        
        rows.append(row)
    
    # Append all tasks
    try:
        body = {'values': rows}
        
        result = service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Action Plans!A:J",
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        print(f"✅ Action plan created successfully!\n")
        print(f"{'='*60}")
        print(f"📌 {goal_name} ({goal_id})")
        print(f"{'='*60}")
        print(f"Plan ID: {plan_id}")
        print(f"Tasks: {len(tasks_list)}")
        print()
        
        for i, task in enumerate(tasks_list, start=1):
            if ':' in task:
                timeline, desc = task.split(':', 1)
                print(f"  □ [{timeline.strip()}] {desc.strip()}")
            else:
                print(f"  □ {task}")
        
        print()
        
        return {
            'success': True,
            'plan_id': plan_id,
            'goal_id': goal_id,
            'task_count': len(tasks_list)
        }
        
    except HttpError as error:
        print(f"❌ Error creating action plan: {error}")
        return {'success': False, 'error': str(error)}

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Create action plan for a goal'
    )
    
    parser.add_argument('goal_id', help='Goal ID (e.g., GOAL-001)')
    parser.add_argument('goal_name', help='Goal name')
    parser.add_argument('--tasks', '-t', help='Semicolon-separated tasks (e.g., "Day 1: Task1;Day 2: Task2")')
    parser.add_argument('--generate', '-g', help='Generate tasks from this context description')
    parser.add_argument('--due', '-d', help='Goal due date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    tasks = []
    if args.generate:
        print(f"🧠 Generating tasks for '{args.goal_name}'...")
        tasks = generate_tasks_from_context(args.goal_name, args.generate, args.due)
        if not tasks:
            print("❌ Failed to generate tasks. Please provide them manually.")
            return 1
    elif args.tasks:
        tasks = [t.strip() for t in args.tasks.split(';') if t.strip()]
    else:
        print("❌ Error: Must provide either --tasks or --generate")
        return 1
    
    result = create_action_plan(
        goal_id=args.goal_id,
        goal_name=args.goal_name,
        tasks_list=tasks,
        goal_due_date=args.due
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
