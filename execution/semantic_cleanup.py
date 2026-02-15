import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def semantic_cleanup():
    print("🧹 Starting semantic cleanup of Knowledge Base...")
    response = supabase.table("knowledge_base").select("*").execute()
    data = response.data
    
    # Heuristic topics: (Keywords, Label)
    topics = [
        (['category', 'หมวดหมู่', 'แก้'], "Category Update Feature"),
        (['goal', 'task', 'ถามก่อน', 'confirm'], "Goal Creation Flow")
    ]
    
    processed_ids = set()
    to_keep = {} # Topic Label -> Item
    to_delete = []
    
    for item in data:
        title = (item['title'] or "").lower()
        content = (item['content'] or "").lower()
        full_text = title + " " + content
        
        assigned_topic = None
        for keywords, label in topics:
            if any(k in full_text for k in keywords):
                assigned_topic = label
                break
        
        if assigned_topic:
            if assigned_topic in to_keep:
                # We already have one for this topic, delete this one
                print(f"🗑️ Found related entry for '{assigned_topic}': '{item['title']}' (ID: {item['id']})")
                to_delete.append(item['id'])
            else:
                # First one we found for this topic, keep it
                print(f"✨ Keeping first entry for '{assigned_topic}': '{item['title']}' (ID: {item['id']})")
                to_keep[assigned_topic] = item
        
    if not to_delete:
        print("✅ No related duplicates found.")
    else:
        print(f"\n🚀 Deleting {len(to_delete)} entries...")
        for entry_id in to_delete:
            res = supabase.table("knowledge_base").delete().eq("id", entry_id).execute()
            print(f"   - Deleted ID: {entry_id}")
            
    print("\n✨ Semantic cleanup complete.")

if __name__ == "__main__":
    semantic_cleanup()
