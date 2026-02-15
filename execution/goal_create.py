import os
import sys
import argparse
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add module path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from execution.llm_utils import LLMClient
    from execution.supabase_db import create_goal as db_create_goal, create_tasks as db_create_tasks
except ImportError:
    try:
        from llm_utils import LLMClient
        from supabase_db import create_goal as db_create_goal, create_tasks as db_create_tasks
    except ImportError:
        LLMClient = None

# Load environment variables
load_dotenv()

def parse_due_date(date_str):
    """Parse due date string into YYYY-MM-DD format."""
    if not date_str:
        return None
    
    if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
        return date_str
    
    date_str_lower = date_str.lower()
    if 'วันนี้' in date_str_lower or 'today' in date_str_lower:
        return datetime.now().strftime('%Y-%m-%d')
    if 'พรุ่งนี้' in date_str_lower or 'tomorrow' in date_str_lower:
        return (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    return date_str

def generate_breakdown(name, description, due_date):
    """Generate sub-tasks using LLM."""
    if not LLMClient:
        return []
    try:
        client = LLMClient()
        prompt = f"""
        ฉันมีเป้าหมาย: "{name}"
        รายละเอียด: {description}
        กำหนดส่ง: {due_date}
        วันที่ปัจจุบัน: {datetime.now().strftime('%Y-%m-%d')}
        
        กรุณาแตกเป้าหมายนี้ออกเป็นขั้นตอนย่อย (sub-tasks) ที่ชัดเจนและทำได้จริง 3-7 รายการ
        ตอบกลับเป็น JSON object ที่มี key 'tasks' ประกอบด้วย list ของ strings
        
        รูปแบบ task: "ระยะเวลา: รายละเอียดงาน" (เช่น "Day 1-2: ทำ market research")
        **สำคัญ: ใช้ภาษาไทยทั้งหมด**
        """
        response = client.generate_json(prompt)
        return response.get('tasks', []) if response else []
    except Exception as e:
        print(f"Warning: Failed to generate breakdown: {e}")
    return []

def breakdown_existing_goal(goal_id):
    """Break down an existing goal into tasks based on its details in Supabase."""
    from execution.supabase_db import get_goal_by_id
    
    print(f"🧠 Breaking down existing goal (ID: {goal_id})...")
    goal = get_goal_by_id(goal_id)
    if not goal:
        print(f"❌ Goal not found: {goal_id}")
        return {'success': False, 'error': 'Goal not found'}
    
    tasks = generate_breakdown(goal['name'], goal.get('description', ''), goal.get('due_date'))
    
    if tasks:
        tasks_data = []
        for t in tasks:
            tasks_data.append({
                "goal_id": goal_id,
                "name": t,
                "status": "Todo",
                "priority": "Medium"
            })
        db_create_tasks(tasks_data)
        print(f"  ✅ Action plan generated with {len(tasks)} tasks.")
        return {'success': True, 'tasks_count': len(tasks)}
    else:
        return {'success': False, 'error': 'Failed to generate tasks'}

def create_goal(name, description='', due_date=None, goal_type='', priority='Medium', reminder='', auto_breakdown=False):
    """Create a new goal in Supabase."""
    print(f"🎯 Creating goal in Supabase: {name}\n")
    
    goal_id = str(uuid.uuid4())[:8]
    parsed_due = parse_due_date(due_date) if due_date else None
    
    goal_data = {
        "id": goal_id,
        "name": name,
        "description": description,
        "category": goal_type,
        "due_date": parsed_due,
        "priority": priority,
        "reminder_schedule": reminder,
        "status": "Active"
    }
    
    try:
        # Create Goal
        db_create_goal(goal_data)
        print(f"✅ Goal created successfully in Supabase (ID: {goal_id})")
        
        # Auto-breakdown
        if auto_breakdown:
            breakdown_existing_goal(goal_id)
        
        return {
            'success': True,
            'goal_id': goal_id,
            'name': name,
            'due_date': parsed_due,
            'status': 'Active'
        }
    except Exception as e:
        print(f"❌ Error creating goal: {e}")
        return {'success': False, 'error': str(e)}

def main():
    parser = argparse.ArgumentParser(description='Create new goal in NOVA II')
    parser.add_argument('name', help='Goal name')
    parser.add_argument('--description', '-d', default='', help='Goal description')
    parser.add_argument('--due', '-D', help='Due date')
    parser.add_argument('--priority', '-p', default='Medium', choices=['High', 'Medium', 'Low'])
    parser.add_argument('--auto-breakdown', '-a', action='store_true')
    
    args = parser.parse_args()
    result = create_goal(name=args.name, description=args.description, due_date=args.due, priority=args.priority, auto_breakdown=args.auto_breakdown)
    return 0 if result['success'] else 1

if __name__ == "__main__":
    sys.exit(main())
