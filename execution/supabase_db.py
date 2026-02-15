import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def get_active_goals():
    """Fetch all active goals from Supabase."""
    response = supabase.table("goals").select("*").eq("status", "Active").execute()
    return response.data

def create_goal(goal_data):
    """Insert a new goal into Supabase."""
    # Ensure ID exists
    if 'id' not in goal_data:
        import uuid
        goal_data['id'] = str(uuid.uuid4())[:8]
        
    response = supabase.table("goals").insert(goal_data).execute()
    return response.data[0] if response.data else None

def create_tasks(tasks_data):
    """Insert multiple tasks into Supabase."""
    response = supabase.table("tasks").insert(tasks_data).execute()
    return response.data

def get_tasks_for_goal(goal_id):
    """Fetch tasks for a specific goal."""
    response = supabase.table("tasks").select("*").eq("goal_id", goal_id).execute()
    return response.data

def update_goal(goal_id, update_data):
    """Update goal fields."""
    response = supabase.table("goals").update(update_data).eq("id", goal_id).execute()
    return response.data
