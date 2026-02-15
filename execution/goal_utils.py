import os
from datetime import datetime
try:
    from execution.supabase_db import get_active_goals as fetch_goals, get_all_active_tasks
except ImportError:
    from supabase_db import get_active_goals as fetch_goals, get_all_active_tasks

def get_active_goals():
    """Fetch active goals from Supabase."""
    print("📋 Starting get_active_goals via Supabase...")
    try:
        goals = fetch_goals()
        print(f"✅ Found {len(goals)} active goals in Supabase.")
        return goals
    except Exception as e:
        print(f"❌ Error in get_active_goals (Supabase): {e}")
        return []

def get_daily_tasks():
    """Fetch all tasks that are currently active/in progress."""
    print("📅 Fetching daily tasks via Supabase...")
    try:
        tasks = get_all_active_tasks()
        print(f"✅ Found {len(tasks)} active tasks in Supabase.")
        return tasks
    except Exception as e:
        print(f"❌ Error in get_daily_tasks (Supabase): {e}")
        return []
