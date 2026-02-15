import os, pickle, json
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()
token_path = 'token.pickle'
if not os.path.exists(token_path):
    print("TOKEN_NOT_FOUND")
    exit(1)

creds = pickle.load(open(token_path, 'rb'))
service = build('sheets', 'v4', credentials=creds)
sheet_id = os.getenv('GOOGLE_SHEET_ID', '194ZhTkYYog4qHGALr0qSYuX4iXvuypELRKoVz_--3DA')

# Get spreadsheet metadata to see all sheets
spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
sheets = spreadsheet.get('sheets', [])

for sheet in sheets:
    title = sheet.get('properties', {}).get('title')
    print(f"\n--- Sheet: {title} ---")
    
    # Get first 2 rows to see headers and sample data
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, 
            range=f"'{title}'!A1:Z5"
        ).execute()
        values = result.get('values', [])
        print(json.dumps(values, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error reading sheet {title}: {e}")
