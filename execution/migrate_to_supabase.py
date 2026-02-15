import os
import sys
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.goal_utils import get_active_goals as get_sheets_goals
from execution.supabase_db import supabase, create_goal, create_tasks

def migrate():
    print("🚀 Starting migration from Google Sheets to Supabase...")
    
    # 1. Fetch from Sheets
    sheets_goals = get_sheets_goals()
    if not sheets_goals:
        print("❌ No active goals found in Google Sheets.")
        return

    print(f"📊 Found {len(sheets_goals)} goals in Sheets.")

    for goal in sheets_goals:
        print(f"📦 Migrating goal: {goal['name']}...")
        
        # Prepare data for Supabase
        supabase_goal = {
            "id": goal['id'],
            "name": goal['name'],
            "description": goal.get('description', ''),
            "due_date": goal.get('due_date', None) or None,
            "status": "Active",
            "priority": goal.get('priority', 'Medium'),
            "progress_notes": goal.get('progress', '')
        }
        
        # Clean up empty dates
        if not supabase_goal["due_date"]:
            del supabase_goal["due_date"]

        try:
            # Insert goal
            create_goal(supabase_goal)
            print(f"✅ Goal '{goal['name']}' migrated.")
        except Exception as e:
            print(f"⚠️ Error migrating goal {goal['id']}: {e}")

    print("\n✨ Migration completed successfully!")
    print("Check your Supabase dashboard to verify.")

if __name__ == "__main__":
    migrate()
