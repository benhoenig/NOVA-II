#!/usr/bin/env python3
"""
Retrieve/search knowledge items from NOVA II Google Sheets.

This script searches across all knowledge sheets and returns relevant results
based on keywords, tags, or natural language queries.

Usage:
    python kb_retrieve.py <query> [--sheet SHEET] [--limit LIMIT]
    
Examples:
    python kb_retrieve.py "pricing strategy"
    python kb_retrieve.py "customer ABC" --sheet Customers
    python kb_retrieve.py "บทเรียน" --limit 5
"""

import os
import sys
import argparse
import re
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

# Knowledge sheets to search
KNOWLEDGE_SHEETS = ['Notes', 'Lessons Learned', 'Business', 'Customers', 'Other']

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

def search_in_sheet(service, spreadsheet_id, sheet_name, query_terms):
    """
    Search for query terms in a specific sheet.
    
    Args:
        service: Google Sheets API service
        spreadsheet_id: ID of the spreadsheet
        sheet_name: Name of the sheet to search
        query_terms: List of search terms (lowercase)
        
    Returns:
        List of matching rows with relevance scores
    """
    try:
        # Get all data from sheet
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:Z"
        ).execute()
        
        values = result.get('values', [])
        
        if len(values) <= 1:  # Only header or empty
            return []
        
        headers = values[0]
        matches = []
        
        # Search through each row
        for i, row in enumerate(values[1:], start=2):  # Skip header
            if not row:
                continue
            
            # Convert row to searchable text
            row_text = ' '.join(str(cell) for cell in row).lower()
            
            # Calculate relevance score
            score = 0
            matched_terms = []
            
            for term in query_terms:
                if term in row_text:
                    # Count occurrences for scoring
                    count = row_text.count(term)
                    score += count
                    matched_terms.append(term)
            
            if score > 0:
                # Create result dict
                result_dict = {}
                for j, header in enumerate(headers):
                    if j < len(row):
                        result_dict[header] = row[j]
                    else:
                        result_dict[header] = ''
                
                matches.append({
                    'sheet': sheet_name,
                    'row_number': i,
                    'score': score,
                    'matched_terms': matched_terms,
                    'data': result_dict
                })
        
        return matches
        
    except HttpError as error:
        print(f"Warning: Could not search sheet '{sheet_name}': {error}")
        return []

def retrieve_knowledge(query, target_sheet=None, limit=10):
    """
    Search and retrieve knowledge items.
    
    Args:
        query: Search query string
        target_sheet: Specific sheet to search (optional)
        limit: Maximum number of results to return
        
    Returns:
        List of matching knowledge items
    """
    print(f"🔍 Searching for: '{query}'\n")
    
    # Get credentials and create service
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    # Get Sheet ID
    sheet_id = os.getenv('GOOGLE_SHEET_ID', DEFAULT_SHEET_ID)
    
    # Prepare search terms (split query into words, lowercase)
    query_terms = [term.lower() for term in re.findall(r'\w+', query)]
    
    # Determine which sheets to search
    sheets_to_search = [target_sheet] if target_sheet else KNOWLEDGE_SHEETS
    
    # Search across sheets
    all_matches = []
    
    for sheet_name in sheets_to_search:
        if sheet_name not in KNOWLEDGE_SHEETS:
            continue
        
        matches = search_in_sheet(service, sheet_id, sheet_name, query_terms)
        all_matches.extend(matches)
    
    # Sort by relevance score
    all_matches.sort(key=lambda x: x['score'], reverse=True)
    
    # Limit results
    results = all_matches[:limit]
    
    # Display results
    if not results:
        print("❌ No matches found")
        return []
    
    print(f"✅ Found {len(results)} result(s):\n")
    
    for i, match in enumerate(results, 1):
        print(f"{'='*60}")
        print(f"Result #{i} (Score: {match['score']})")
        print(f"Sheet: {match['sheet']}")
        print(f"{'='*60}")
        
        data = match['data']
        
        # Display based on sheet type
        if match['sheet'] == 'Notes':
            print(f"ID: {data.get('Note ID', '')}")
            print(f"Title: {data.get('Title', '')}")
            print(f"Content: {data.get('Content', '')}")
            print(f"Category: {data.get('Category', '')}")
            print(f"Tags: {data.get('Tags', '')}")
            print(f"Created: {data.get('Created Date', '')}")
            
        elif match['sheet'] == 'Lessons Learned':
            print(f"ID: {data.get('Lesson ID', '')}")
            print(f"Title: {data.get('Title', '')}")
            print(f"What Happened: {data.get('What Happened', '')}")
            print(f"What I Learned: {data.get('What I Learned', '')}")
            print(f"How to Apply: {data.get('How to Apply', '')}")
            print(f"Category: {data.get('Category', '')}")
            
        elif match['sheet'] == 'Business':
            print(f"ID: {data.get('Entry ID', '')}")
            print(f"Topic: {data.get('Topic', '')}")
            print(f"Content: {data.get('Content', '')}")
            print(f"Category: {data.get('Category', '')}")
            print(f"Tags: {data.get('Tags', '')}")
            
        elif match['sheet'] == 'Customers':
            print(f"ID: {data.get('Contact ID', '')}")
            print(f"Name: {data.get('Name', '')}")
            print(f"Type: {data.get('Type', '')}")
            print(f"Company: {data.get('Company', '')}")
            print(f"Notes: {data.get('Notes', '')}")
            print(f"Last Contact: {data.get('Last Contact', '')}")
            
        else:  # Other
            print(f"ID: {data.get('Entry ID', '')}")
            print(f"Title: {data.get('Title', '')}")
            print(f"Content: {data.get('Content', '')}")
            print(f"Category: {data.get('Category', '')}")
        
        print()
    
    return results

def main():
    """Main function to parse arguments and retrieve knowledge."""
    parser = argparse.ArgumentParser(
        description='Search and retrieve knowledge from NOVA II'
    )
    
    parser.add_argument('query', help='Search query')
    parser.add_argument('--sheet', '-s', help='Specific sheet to search')
    parser.add_argument('--limit', '-l', type=int, default=10, help='Maximum results (default: 10)')
    
    args = parser.parse_args()
    
    results = retrieve_knowledge(
        query=args.query,
        target_sheet=args.sheet,
        limit=args.limit
    )
    
    return 0 if results else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Search cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
