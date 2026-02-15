import os
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("⚠️ WARNING: SUPABASE_URL or SUPABASE_KEY is not set!")

supabase: Client = create_client(url or "https://placeholder.supabase.co", key or "placeholder")

def parse_supabase_error(e):
    """Parse common Supabase/PostgREST errors and return a user-friendly message or code."""
    error_str = str(e)
    if "PGRST204" in error_str:
        return "SCHEMA_MISMATCH", "พบปัญหาโครงสร้างตารางไม่ตรงกับข้อมูล (Schema Mismatch) รบกวนกด 'Reload Schema' ในหน้า Supabase Dashboard ค่ะ"
    if "PGRST200" in error_str:
        return "TABLE_NOT_FOUND", "ไม่พบตารางที่ต้องการเข้าถึงในฐานข้อมูลค่ะ"
    return "UNKNOWN_ERROR", error_str

def get_active_goals():
    """Fetch all active goals from Supabase."""
    response = supabase.table("goals").select("*").eq("status", "Active").order("created_at", desc=True).execute()
    return response.data

def get_all_active_tasks():
    """Fetch all tasks that are not 'Done' or 'Cancelled' across all goals."""
    response = supabase.table("tasks") \
        .select("*, goals(name, due_date)") \
        .not_.in_("status", ["Done", "Cancelled"]) \
        .order("due_date", desc=False) \
        .execute()
    return response.data

def get_task_by_name_partial(name_query):
    """Find tasks by partial name match."""
    response = supabase.table("tasks") \
        .select("*, goals(name)") \
        .ilike("name", f"%{name_query}%") \
        .order("created_at", desc=True) \
        .limit(5) \
        .execute()
    return response.data

def search_knowledge(query):
    """Search for keywords across knowledge_base, goals, and business tables."""
    results = {}
    
    # Simple search using ilike on multiple tables
    # Knowledge Base
    kb_res = supabase.table("knowledge_base") \
        .select("*") \
        .or_(f"title.ilike.%{query}%,content.ilike.%{query}%") \
        .limit(5).execute()
    results['knowledge'] = kb_res.data
    
    # Goals
    goal_res = supabase.table("goals") \
        .select("*") \
        .or_(f"name.ilike.%{query}%,description.ilike.%{query}%") \
        .limit(5).execute()
    results['goals'] = goal_res.data
    
    # Business
    bus_res = supabase.table("business_portfolio") \
        .select("*") \
        .or_(f"name.ilike.%{query}%,description.ilike.%{query}%") \
        .limit(5).execute()
    results['business'] = bus_res.data
    
    return results

def create_goal(goal_data):
    """Insert a new goal into Supabase."""
    # Ensure ID exists
    if 'id' not in goal_data:
        goal_data['id'] = str(uuid.uuid4())[:8]
        
    response = supabase.table("goals").insert(goal_data).execute()
    return response.data[0] if response.data else None

def store_knowledge(data):
    """
    Store knowledge item (note, lesson, etc.) into Supabase.
    
    Includes duplicate detection: checks for similar existing entries
    and returns info if one is found instead of inserting a duplicate.
    """
    # Ensure ID
    if 'id' not in data or not data['id']:
        data['id'] = f"NOTE-{str(uuid.uuid4())[:6]}"
    
    # Check for similar existing entries (basic duplicate prevention)
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    
    if title:
        try:
            # Search for entries with same or very similar title
            existing = supabase.table("knowledge_base") \
                .select("*") \
                .ilike("title", f"%{title}%") \
                .limit(5) \
                .execute()
            
            # Check if any result is close enough to be considered a duplicate
            for item in existing.data:
                existing_title = (item.get('title') or '').strip()
                # If titles are very similar (>80% match), consider it a duplicate
                if existing_title and title.lower() in existing_title.lower():
                    return {
                        'duplicate_found': True,
                        'existing_id': item['id'],
                        'existing_title': item['title'],
                        'suggestion': 'update_existing'
                    }
        except Exception as e:
            # If similarity check fails, proceed with insert
            print(f"⚠️ Similarity check failed: {e}")
    
    response = supabase.table("knowledge_base").insert(data).execute()
    return response.data[0] if response.data else None

def create_tasks(tasks_data):
    """Insert multiple tasks into Supabase with retry logic for schema issues."""
    try:
        response = supabase.table("tasks").insert(tasks_data).execute()
        return response.data
    except Exception as e:
        err_code, msg = parse_supabase_error(e)
        if err_code == "SCHEMA_MISMATCH":
            print(f"⚠️ Schema mismatch detected. Attempting retry without optional columns...")
            # Retry with minimal data (name and goal_id only)
            minimal_tasks = []
            for t in tasks_data:
                minimal_tasks.append({
                    "goal_id": t.get("goal_id"),
                    "name": t.get("name"),
                    "status": t.get("status", "Todo")
                })
            try:
                response = supabase.table("tasks").insert(minimal_tasks).execute()
                print("✅ Retry successful with minimal task data.")
                return response.data
            except Exception as e2:
                print(f"❌ Retry also failed: {e2}")
                raise e2
        raise e

def get_tasks_for_goal(goal_id):
    """Fetch tasks for a specific goal."""
    response = supabase.table("tasks").select("*").eq("goal_id", goal_id).execute()
    return response.data

def update_goal(goal_id, update_data):
    """Update goal fields."""
    response = supabase.table("goals").update(update_data).eq("id", goal_id).execute()
    return response.data

# --- Chat History / Memory ---

def save_chat_message(user_id, role, message, intent=None):
    """Save a message to the chat history table."""
    data = {
        "user_id": user_id,
        "role": role,
        "message": message,
        "intent": intent
    }
    supabase.table("chat_history").insert(data).execute()

def get_chat_history(user_id, limit=10):
    """Retrieve the most recent messages for a user."""
    response = supabase.table("chat_history") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()
    # Reverse to get chronological order for the LLM
    return list(reversed(response.data)) if response.data else []

def delete_goal(goal_id):
    """Delete a goal and its associated tasks (managed by CASCADE)."""
    response = supabase.table("goals").delete().eq("id", goal_id).execute()
    return response.data

def delete_task(task_id):
    """Delete a specific task by ID."""
    response = supabase.table("tasks").delete().eq("id", task_id).execute()
    return response.data

def update_task(task_id, update_data):
    """Update task fields (e.g., status, due_date) with basic error handling."""
    try:
        response = supabase.table("tasks").update(update_data).eq("id", task_id).execute()
        return response.data
    except Exception as e:
        err_code, msg = parse_supabase_error(e)
        print(f"❌ Error updating task: {msg}")
        return None

def get_goal_by_id(goal_id):
    """Fetch a specific goal by ID."""
    response = supabase.table("goals").select("*").eq("id", goal_id).execute()
    return response.data[0] if response.data else None

def update_knowledge(item_id, update_data):
    """Update knowledge base item fields (e.g., category)."""
    response = supabase.table("knowledge_base").update(update_data).eq("id", item_id).execute()
    return response.data
