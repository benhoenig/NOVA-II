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
result = service.spreadsheets().values().get(spreadsheetId=sheet_id, range='Goals!A1:M10').execute()
print(json.dumps(result.get('values', []), ensure_ascii=False, indent=2))
