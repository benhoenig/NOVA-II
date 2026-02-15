import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def audit_and_cleanup():
    print("🔍 Auditing Knowledge Base for duplicates...")
    response = supabase.table("knowledge_base").select("*").execute()
    data = response.data
    
    seen = {} # (title, content) -> list of IDs
    to_delete = []
    
    for item in data:
        # Standardize for comparison (remove whitespace)
        title_stripped = item['title'].strip() if item['title'] else ""
        content_stripped = item['content'].strip() if item['content'] else ""
        key = (title_stripped, content_stripped)
        
        if key in seen:
            print(f"⚠️ Duplicate found: '{item['title']}' (ID: {item['id']})")
            to_delete.append(item['id'])
        else:
            seen[key] = item['id']
            
    if not to_delete:
        print("✅ No duplicates found.")
    else:
        print(f"\n🗑️ Deleting {len(to_delete)} duplicate entries...")
        for entry_id in to_delete:
            res = supabase.table("knowledge_base").delete().eq("id", entry_id).execute()
            print(f"   - Deleted ID: {entry_id}")
            
    print("\n✨ Audit and cleanup complete.")

if __name__ == "__main__":
    audit_and_cleanup()
