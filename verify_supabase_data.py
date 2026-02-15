import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from execution.supabase_db import get_active_goals

load_dotenv()

def list_goals():
    print("🔍 Fetching goals from Supabase...")
    goals = get_active_goals()
    if not goals:
        print("ℹ️ No active goals found.")
        return

    print(f"✅ Found {len(goals)} active goals:\n")
    for i, g in enumerate(goals, 1):
        print(f"{i}. [{g['id']}] {g['name']}")
        print(f"   - Description: {g['description']}")
        print(f"   - Due: {g['due_date']}")
        print(f"   - Priority: {g['priority']}")
        print(f"   - Status: {g['status']}")
        print("-" * 30)

if __name__ == "__main__":
    list_goals()
