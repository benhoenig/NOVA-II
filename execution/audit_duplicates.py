import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def audit():
    print("🔍 Auditing Knowledge Base for duplicates...")
    response = supabase.table("knowledge_base").select("*").execute()
    data = response.data
    
    seen = {} # (title, content) -> list of IDs
    duplicates = []
    
    for item in data:
        key = (item['title'], item['content'])
        if key in seen:
            seen[key].append(item['id'])
            duplicates.append(item)
        else:
            seen[key] = [item['id']]
            
    if not duplicates:
        print("✅ No duplicates found.")
    else:
        print(f"⚠️ Found {len(duplicates)} duplicate entries:")
        for item in duplicates:
            print(f"- ID: {item['id']} | Title: {item['title']} | Category: {item['category']}")
            
    return seen

if __name__ == "__main__":
    audit()
