import os
from datetime import datetime
from execution.supabase_db import get_active_goals as fetch_goals

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
    """Fetch tasks due today or high priority."""
    # For now, just return active goals as a summary
    return get_active_goals()
