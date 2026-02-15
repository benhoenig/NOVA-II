
from execution.supabase_db import supabase

def log_action(action_type, description, details=None):
    """
    Log an action to the history_logs table.
    
    Args:
        action_type (str): Category of action (e.g., 'CREATE_GOAL', 'COMPLETE_TASK')
        description (str): Human-readable summary
        details (dict, optional): proper structured data for the action
    """
    try:
        data = {
            "action_type": action_type,
            "description": description,
            "details": details or {}
        }
        # created_at is handled by default value in schema
        supabase.table("history_logs").insert(data).execute()
        return True
    except Exception as e:
        # We don't want logging failures to crash the main app
        print(f"⚠️ Failed to log action: {e}")
        return False
