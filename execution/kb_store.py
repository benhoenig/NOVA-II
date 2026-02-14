#!/usr/bin/env python3
"""
Store knowledge items in NOVA II Google Sheets.

This script stores information in the appropriate sheet based on category
and auto-categorizes if category is not specified.

Usage:
    python kb_store.py <title> <content> [--category CATEGORY] [--tags TAGS]
    
Examples:
    python kb_store.py "Meeting Notes" "Discussed Q1 goals" --category "Notes"
    python kb_store.py "Price Strategy" "Must set clear prices upfront" --category "Lessons" --tags "business,pricing"
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
import re

# Load environment variables
load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
DEFAULT_SHEET_ID = '194ZhTkYYog4qHGALr0qSYuX4iXvuypELRKoVz_--3DA'

# Category mapping
CATEGORY_MAP = {
    'notes': 'Notes',
    'note': 'Notes',
    'บันทึก': 'Notes',
    'lessons': 'Lessons Learned',
    'lesson': 'Lessons Learned',
    'บทเรียน': 'Lessons Learned',
    'lesson learned': 'Lessons Learned',
    'business': 'Business',
    'ธุรกิจ': 'Business',
    'customers': 'Customers',
    'customer': 'Customers',
    'ลูกค้า': 'Customers',
    'contacts': 'Customers',
    'contact': 'Customers',
    'other': 'Other',
    'อื่นๆ': 'Other'
}

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

def normalize_category(category):
    """Normalize category name to match sheet names."""
    if not category:
        return 'Other'
    
    category_lower = category.lower().strip()
    return CATEGORY_MAP.get(category_lower, 'Other')

def generate_id(sheet_name, service, spreadsheet_id):
    """Generate unique ID for the entry."""
    # Get prefix based on sheet
    prefixes = {
        'Notes': 'NOTE',
        'Lessons Learned': 'LES',
        'Business': 'BUS',
        'Customers': 'CONT',
        'Other': 'OTH'
    }
    
    prefix = prefixes.get(sheet_name, 'GEN')
    
    # Get current row count to generate next ID
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:A"
        ).execute()
        
        values = result.get('values', [])
        # Subtract 1 for header row
        count = len(values)
        next_id = f"{prefix}-{count:03d}"
        
        return next_id
    except:
        return f"{prefix}-001"

def store_knowledge(title, content, category=None, tags=None):
    """
    Store knowledge item in appropriate Google Sheet.
    
    Args:
        title: Title of the knowledge item
        content: Full content/description
        category: Category (will be normalized)
        tags: Comma-separated tags
    """
    print(f"📝 Storing knowledge item...\n")
    
    # Get credentials and create service
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    # Get Sheet ID
    sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
    
    # Normalize category
    sheet_name = normalize_category(category)
    print(f"Category: {sheet_name}")
    
    # Generate ID
    entry_id = generate_id(sheet_name, service, sheet_id)
    print(f"ID: {entry_id}")
    
    # Get current timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Prepare row data based on sheet type
    row_data = None
    
    if sheet_name == 'Notes':
        # Notes: Note ID, Title, Content, Category, Tags, Created Date, Last Modified, Source/Reference
        row_data = [entry_id, title, content, category or '', tags or '', timestamp, timestamp, '']
        
    elif sheet_name == 'Lessons Learned':
        # Lessons: Lesson ID, Title, What Happened, What I Learned, How to Apply, Category, Date, Created Date
        # For now, put everything in content, user can refine later
        row_data = [entry_id, title, content, '', '', category or 'General', timestamp, timestamp]
        
    elif sheet_name == 'Business':
        # Business: Entry ID, Topic, Content, Category, Related To, Tags, Created Date, Last Modified
        row_data = [entry_id, title, content, category or '', '', tags or '', timestamp, timestamp]
        
    elif sheet_name == 'Customers':
        # Customers: Contact ID, Name, Type, Company, Contact Info, Notes, Last Contact, Tags, Created Date
        row_data = [entry_id, title, category or 'Contact', '', '', content, timestamp, tags or '', timestamp]
        
    else:  # Other
        # Other: Entry ID, Title, Content, Category, Tags, Created Date, Last Modified
        row_data = [entry_id, title, content, category or '', tags or '', timestamp, timestamp]
    
    # Append to sheet
    try:
        range_name = f"{sheet_name}!A:Z"
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
        
        print(f"\n✅ Stored successfully!")
        print(f"Sheet: {sheet_name}")
        print(f"ID: {entry_id}")
        print(f"Title: {title}")
        
        return {
            'success': True,
            'id': entry_id,
            'sheet': sheet_name,
            'title': title
        }
        
    except HttpError as error:
        print(f"\n❌ Error storing knowledge: {error}")
        return {'success': False, 'error': str(error)}

def main():
    """Main function to parse arguments and store knowledge."""
    parser = argparse.ArgumentParser(
        description='Store knowledge items in NOVA II Google Sheets'
    )
    
    parser.add_argument('title', help='Title of the knowledge item')
    parser.add_argument('content', help='Full content/description')
    parser.add_argument('--category', '-c', help='Category (Notes, Lessons, Business, Customers, Other)')
    parser.add_argument('--tags', '-t', help='Comma-separated tags')
    
    args = parser.parse_args()
    
    result = store_knowledge(
        title=args.title,
        content=args.content,
        category=args.category,
        tags=args.tags
    )
    
    return 0 if result['success'] else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
