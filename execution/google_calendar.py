#!/usr/bin/env python3
"""
Google Calendar integration for NOVA II.

Provides functions to list, create, update, and delete Google Calendar events.
Uses the same OAuth credential pattern as goal_reminders.py.

Usage:
    python google_calendar.py list [--days 7]
    python google_calendar.py create --summary "Meeting" --date 2026-02-20 --start 14:00 --end 15:00
    python google_calendar.py delete --event-id <id>
"""

import os
import sys
import argparse
import json
import pickle
import base64
from datetime import datetime, timedelta

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# Scopes — includes Calendar + existing scopes for shared token
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.events',
]

# Timezone for Bangkok
TIMEZONE = 'Asia/Bangkok'


def get_credentials():
    """Get or refresh Google API credentials.
    
    Follows the same pattern as goal_reminders.py:
    1. Environment variable GOOGLE_TOKEN_JSON
    2. Base64 pickle fallback GOOGLE_TOKEN_BASE64
    3. Local token.pickle file
    4. Re-auth via credentials.json
    """
    creds = None

    # 1. Try reading from environment variable (JSON string)
    token_json = os.getenv('GOOGLE_TOKEN_JSON')
    if token_json:
        try:
            creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        except Exception as e:
            print(f"❌ Error loading GOOGLE_TOKEN_JSON: {e}")

    # 2. Try Base64 encoded pickle (deprecated fallback)
    if not creds:
        token_b64 = os.getenv('GOOGLE_TOKEN_BASE64')
        if token_b64:
            try:
                creds_data = base64.b64decode(token_b64)
                creds = pickle.loads(creds_data)
            except Exception as e:
                print(f"❌ Error decoding GOOGLE_TOKEN_BASE64: {e}")

    # 3. Fallback to local files
    if not creds:
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        elif os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

    # 4. Refresh or re-auth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json not found!")
                print("Please run setup first. See GOOGLE_SETUP.md")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save refreshed token
        try:
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        except Exception:
            pass

    return creds


def get_calendar_service():
    """Get authenticated Google Calendar service."""
    creds = get_credentials()
    if not creds:
        return None
    return build('calendar', 'v3', credentials=creds)


def list_events(days=7, max_results=20):
    """List upcoming events for the next N days.
    
    Args:
        days: Number of days ahead to look (default 7)
        max_results: Maximum number of events to return
        
    Returns:
        list of event dicts with: id, summary, start, end, location, description
    """
    service = get_calendar_service()
    if not service:
        return []

    now = datetime.utcnow()
    time_min = now.isoformat() + 'Z'
    time_max = (now + timedelta(days=days)).isoformat() + 'Z'

    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        result = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))

            result.append({
                'id': event['id'],
                'summary': event.get('summary', '(No title)'),
                'start': start,
                'end': end,
                'location': event.get('location', ''),
                'description': event.get('description', ''),
                'all_day': 'date' in event['start']  # True if all-day
            })

        return result

    except HttpError as error:
        print(f"❌ Error listing events: {error}")
        return []


def create_event(summary, start_time, end_time, description=None,
                 location=None, all_day=False):
    """Create a new calendar event.
    
    Args:
        summary: Event title
        start_time: Start time as string (ISO format or 'YYYY-MM-DD' for all-day)
        end_time: End time as string (ISO format or 'YYYY-MM-DD' for all-day)
        description: Optional event description
        location: Optional location
        all_day: If True, creates an all-day event
        
    Returns:
        dict with event details on success, None on failure
    """
    service = get_calendar_service()
    if not service:
        return None

    event_body = {
        'summary': summary,
    }

    if all_day:
        # All-day event uses 'date' instead of 'dateTime'
        event_body['start'] = {'date': start_time}
        event_body['end'] = {'date': end_time}
    else:
        # Timed event
        event_body['start'] = {
            'dateTime': start_time,
            'timeZone': TIMEZONE,
        }
        event_body['end'] = {
            'dateTime': end_time,
            'timeZone': TIMEZONE,
        }

    if description:
        event_body['description'] = description
    if location:
        event_body['location'] = location

    try:
        event = service.events().insert(
            calendarId='primary',
            body=event_body
        ).execute()

        return {
            'success': True,
            'id': event['id'],
            'summary': event.get('summary'),
            'start': event['start'].get('dateTime', event['start'].get('date')),
            'end': event['end'].get('dateTime', event['end'].get('date')),
            'link': event.get('htmlLink', ''),
        }

    except HttpError as error:
        print(f"❌ Error creating event: {error}")
        return None


def delete_event(event_id):
    """Delete a calendar event by ID.
    
    Args:
        event_id: Google Calendar event ID
        
    Returns:
        dict with success status
    """
    service = get_calendar_service()
    if not service:
        return {'success': False, 'error': 'No calendar service'}

    try:
        service.events().delete(
            calendarId='primary',
            eventId=event_id
        ).execute()
        return {'success': True}

    except HttpError as error:
        print(f"❌ Error deleting event: {error}")
        return {'success': False, 'error': str(error)}


def find_event_by_name(name, days=30):
    """Find events matching a name/summary (case-insensitive partial match).
    
    Args:
        name: Search query for event summary
        days: How many days ahead to search
        
    Returns:
        list of matching events
    """
    service = get_calendar_service()
    if not service:
        return []

    now = datetime.utcnow()
    time_min = now.isoformat() + 'Z'
    time_max = (now + timedelta(days=days)).isoformat() + 'Z'

    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            q=name,  # Google Calendar search query
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        return [{
            'id': e['id'],
            'summary': e.get('summary', '(No title)'),
            'start': e['start'].get('dateTime', e['start'].get('date')),
            'end': e['end'].get('dateTime', e['end'].get('date')),
        } for e in events]

    except HttpError as error:
        print(f"❌ Error searching events: {error}")
        return []


def format_events_thai(events):
    """Format a list of events into a readable Thai string.
    
    Args:
        events: List of event dicts from list_events()
        
    Returns:
        Formatted string for chat display
    """
    if not events:
        return "📅 ไม่มี events ที่กำลังจะมาถึงค่ะ"

    lines = []
    current_date = None

    for event in events:
        start_str = event['start']
        
        if event.get('all_day'):
            # All-day event
            dt = datetime.strptime(start_str, '%Y-%m-%d')
            date_label = dt.strftime('%d %b %Y')
            if date_label != current_date:
                current_date = date_label
                lines.append(f"\n📆 {date_label}")
            lines.append(f"  🔹 ทั้งวัน — {event['summary']}")
        else:
            # Timed event — parse ISO datetime
            try:
                dt = datetime.fromisoformat(start_str)
                date_label = dt.strftime('%d %b %Y')
                start_time = dt.strftime('%H:%M')

                end_str = event['end']
                end_dt = datetime.fromisoformat(end_str)
                end_time = end_dt.strftime('%H:%M')

                if date_label != current_date:
                    current_date = date_label
                    lines.append(f"\n📆 {date_label}")
                
                loc = f" 📍 {event['location']}" if event.get('location') else ""
                lines.append(f"  🔹 {start_time} - {end_time} ⟶ {event['summary']}{loc}")
            except Exception:
                lines.append(f"  🔹 {event['summary']} ({start_str})")

    return "📅 ตารางที่กำลังจะมาถึง:\n" + "\n".join(lines)


def parse_datetime_thai(date_str, time_str=None):
    """Parse Thai-friendly date/time strings into ISO format.
    
    Supports:
        - 'วันนี้', 'พรุ่งนี้', 'มะรืนนี้'
        - 'YYYY-MM-DD'
        - 'DD/MM/YYYY'
        - Time: 'HH:MM', 'บ่าย 2' → 14:00
        
    Returns:
        ISO datetime string
    """
    from datetime import date as dt_date

    # Resolve date
    today = datetime.now()

    if not date_str or date_str in ('วันนี้', 'today'):
        target_date = today
    elif date_str in ('พรุ่งนี้', 'tomorrow'):
        target_date = today + timedelta(days=1)
    elif date_str in ('มะรืนนี้', 'day after tomorrow'):
        target_date = today + timedelta(days=2)
    else:
        # Try common formats
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                target_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        else:
            target_date = today

    if not time_str:
        return target_date.strftime('%Y-%m-%d')

    # Parse time
    hour, minute = 0, 0
    if ':' in time_str:
        parts = time_str.replace('.', ':').split(':')
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    elif 'บ่าย' in time_str or 'pm' in time_str.lower():
        import re
        nums = re.findall(r'\d+', time_str)
        if nums:
            hour = int(nums[0])
            if hour < 12:
                hour += 12
    elif 'เช้า' in time_str or 'am' in time_str.lower():
        import re
        nums = re.findall(r'\d+', time_str)
        if nums:
            hour = int(nums[0])

    result_dt = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return result_dt.isoformat()


# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(description='NOVA II Google Calendar')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # list
    list_parser = subparsers.add_parser('list', help='List upcoming events')
    list_parser.add_argument('--days', type=int, default=7, help='Days ahead')

    # create
    create_parser = subparsers.add_parser('create', help='Create event')
    create_parser.add_argument('--summary', required=True, help='Event title')
    create_parser.add_argument('--date', required=True, help='Date (YYYY-MM-DD)')
    create_parser.add_argument('--start', required=True, help='Start time (HH:MM)')
    create_parser.add_argument('--end', required=True, help='End time (HH:MM)')
    create_parser.add_argument('--description', help='Description')
    create_parser.add_argument('--location', help='Location')

    # delete
    delete_parser = subparsers.add_parser('delete', help='Delete event')
    delete_parser.add_argument('--event-id', required=True, help='Event ID')

    # search
    search_parser = subparsers.add_parser('search', help='Search events by name')
    search_parser.add_argument('--name', required=True, help='Search query')

    args = parser.parse_args()

    if args.command == 'list':
        events = list_events(days=args.days)
        print(format_events_thai(events))

    elif args.command == 'create':
        start_iso = f"{args.date}T{args.start}:00"
        end_iso = f"{args.date}T{args.end}:00"
        result = create_event(
            summary=args.summary,
            start_time=start_iso,
            end_time=end_iso,
            description=args.description,
            location=args.location
        )
        if result and result.get('success'):
            print(f"✅ Created event: {result['summary']}")
            print(f"   📅 {result['start']} → {result['end']}")
            print(f"   🔗 {result['link']}")
        else:
            print("❌ Failed to create event")

    elif args.command == 'delete':
        result = delete_event(args.event_id)
        if result.get('success'):
            print("✅ Event deleted")
        else:
            print(f"❌ Failed: {result.get('error')}")

    elif args.command == 'search':
        events = find_event_by_name(args.name)
        if events:
            for e in events:
                print(f"📌 {e['summary']} | {e['start']} | ID: {e['id']}")
        else:
            print("🔍 No events found")

    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
