import os
import sys
import pickle
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build

# Add current directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.supabase_db import supabase

load_dotenv()

def get_sheets_service():
    token_path = 'token.pickle'
    creds = pickle.load(open(token_path, 'rb'))
    return build('sheets', 'v4', credentials=creds)

def migrate_sheet(sheet_name, table_name, mapping_func):
    print(f"📦 Migrating sheet: {sheet_name} -> table: {table_name}...")
    service = get_sheets_service()
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, 
            range=f"'{sheet_name}'!A:Z"
        ).execute()
        
        values = result.get('values', [])
        if len(values) <= 1:
            print(f"ℹ️ No data in {sheet_name}.")
            return

        headers = values[0]
        data_rows = values[1:]
        
        supabase_data = []
        for row in data_rows:
            # Pad row with empty strings if it's shorter than headers
            padding = [''] * (len(headers) - len(row))
            padded_row = list(row) + padding
            # Create a dict from headers and row
            row_dict = dict(zip(headers, padded_row))
            
            mapped = mapping_func(row_dict)
            if mapped:
                supabase_data.append(mapped)

        if supabase_data:
            # Batch insert
            supabase.table(table_name).upsert(supabase_data).execute()
            print(f"✅ Migrated {len(supabase_data)} rows to {table_name}.")
    except Exception as e:
        print(f"❌ Error migrating {sheet_name}: {e}")

def map_goal(row):
    return {
        "id": row.get("Goal ID"),
        "name": row.get("Goal Name"),
        "description": row.get("Description"),
        "category": row.get("Type/Category"),
        "start_date": row.get("Start Date") or None,
        "due_date": row.get("Due Date") or None,
        "status": row.get("Status") or "Active",
        "priority": row.get("Priority") or "Medium",
        "reminder_schedule": row.get("Reminder Schedule"),
        "progress_notes": row.get("Progress Notes"),
        "created_at": row.get("Created Date") or datetime.now().isoformat()
    }

def map_task(row):
    desc = row.get("Task Description")
    if not desc: return None
    return {
        "plan_id": row.get("Plan ID"),
        "goal_id": row.get("Goal ID"),
        "name": desc,
        "timeline": row.get("Timeline"),
        "status": row.get("Status") or "Todo",
        "due_date": row.get("Due Date") or None,
        "notes": row.get("Notes")
    }

def map_note(row):
    tags_str = row.get("Tags", "")
    tags = [t.strip() for t in tags_str.split(",")] if tags_str else []
    ref = row.get("Source/Reference", "")
    goal_id = None
    business_id = None
    
    global_goals = getattr(migrate_all, 'goal_ids', set())
    global_business = getattr(migrate_all, 'business_ids', set())

    if "GOAL-" in ref:
        match = re.search(r"GOAL-\d+", ref)
        if match:
            extracted_id = match.group()
            if extracted_id in global_goals:
                goal_id = extracted_id
    if "BUS-" in ref:
        match = re.search(r"BUS-\d+", ref)
        if match:
            extracted_id = match.group()
            if extracted_id in global_business:
                business_id = extracted_id
        
    return {
        "id": row.get("Note ID"),
        "title": row.get("Title"),
        "content": row.get("Content"),
        "category": row.get("Category"),
        "tags": tags,
        "source_reference": ref,
        "goal_id": goal_id,
        "business_id": business_id,
        "created_at": row.get("Created Date") or datetime.now().isoformat(),
        "updated_at": row.get("Last Modified") or datetime.now().isoformat()
    }

def map_business(row):
    return {
        "id": row.get("Business ID"),
        "name": row.get("Business Name"),
        "description": row.get("Description"),
        "status": row.get("Status"),
        "business_model": row.get("Business Model"),
        "target_customer": row.get("Target Customer"),
        "revenue_model": row.get("Revenue Model"),
        "current_stage": row.get("Current Stage"),
        "monthly_revenue": float(row.get("Monthly Revenue")) if row.get("Monthly Revenue") and row.get("Monthly Revenue").replace('.','',1).isdigit() else 0,
        "customer_count": int(row.get("Customer Count")) if row.get("Customer Count") and row.get("Customer Count").isdigit() else 0,
        "pain_points": row.get("Pain Points"),
        "next_steps": row.get("Next Steps"),
        "related_goals": row.get("Related Goals"),
        "notes": row.get("Notes"),
        "started_date": row.get("Started Date") or None
    }

def map_customer(row):
    tags_str = row.get("Tags", "")
    tags = [t.strip() for t in tags_str.split(",")] if tags_str else []
    return {
        "id": row.get("Contact ID"),
        "name": row.get("Name"),
        "contact_type": row.get("Type"),
        "company": row.get("Company"),
        "contact_info": row.get("Contact Info"),
        "notes": row.get("Notes"),
        "last_contact": row.get("Last Contact") or None,
        "tags": tags
    }

def migrate_all():
    print("🚀 Starting ENHANCED FULL migration to Supabase...")
    service = get_sheets_service()
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    
    # Pre-fetch IDs for FK safety
    try:
        goal_result = service.spreadsheets().values().get(spreadsheetId=sheet_id, range="Goals!A:A").execute()
        migrate_all.goal_ids = {row[0] for row in goal_result.get('values', [])[1:] if row}
    except: migrate_all.goal_ids = set()

    try:
        bus_result = service.spreadsheets().values().get(spreadsheetId=sheet_id, range="'Business Portfolio'!A:A").execute()
        migrate_all.business_ids = {row[0] for row in bus_result.get('values', [])[1:] if row}
    except: migrate_all.business_ids = set()

    migrate_sheet("Business Portfolio", "business_portfolio", map_business)
    migrate_sheet("Goals", "goals", map_goal)
    migrate_sheet("Action Plans", "tasks", map_task)
    migrate_sheet("Notes", "knowledge_base", map_note)
    migrate_sheet("Customers", "customers", map_customer)
    print("\n✨ Migration finished!")

if __name__ == "__main__":
    migrate_all()
