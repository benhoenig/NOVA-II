import os
from supabase import create_client
from dotenv import load_dotenv

def cleanup_goals():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)

    # 1. Fetch all goals and their task counts
    response = supabase.table("goals").select("id, name, created_at").execute()
    goals = response.data
    
    if not goals:
        print("No goals found.")
        return

    # User's target: "Product Discovery"
    # We will keep the cleanest "Product Discovery" entry.
    # Looking at the list, ID: 94a1fd72 Name: Product Discovery looks like the one.
    # Everything else related to Schema, access, or system setup should be removed.

    keep_id = "94a1fd72" # The clean one
    to_delete = []

    for g in goals:
        if g['id'] == keep_id:
            print(f"✅ Keeping product discovery goal: {g['id']} - {g['name']}")
            continue
        
        # Mark for deletion
        to_delete.append(g['id'])
        print(f"🗑️ Marking for deletion: {g['id']} - {g['name']}")

    if not to_delete:
        print("No goals marked for deletion.")
        return

    # 2. Execute deletion (Cascade should handle tasks if foreign key is set correctly)
    # If not cascade, we'd need to delete tasks first. My audit showed 0 tasks for most.
    # Let's check for tasks linked to ANY of these first.
    
    for goal_id in to_delete:
        # Delete tasks first just in case
        supabase.table("tasks").delete().eq("goal_id", goal_id).execute()
        # Delete goal
        supabase.table("goals").delete().eq("id", goal_id).execute()
        print(f"  Done: {goal_id}")

if __name__ == "__main__":
    cleanup_goals()
