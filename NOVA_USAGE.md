# NOVA II Usage Guide

Welcome to NOVA II, your personal AI assistant! This guide shows you how to use all features.

## First-Time Setup

### 1. Set up Google OAuth (One-time)

Follow the detailed instructions in [GOOGLE_SETUP.md](file:///Users/benpoovaviranon/Desktop/Ben/AI%20&%20Automation/NOVA%20II/GOOGLE_SETUP.md) to:

1. Create Google Cloud project
2. Enable Google Sheets API  
3. Download `credentials.json`
4. Place it in your project directory

### 2. Initialize Google Sheets (One-time)

```bash
cd "/Users/benpoovaviranon/Desktop/Ben/AI & Automation/NOVA II"
source venv/bin/activate
python execution/initialize_sheets.py
```

This will:
- Prompt you to authenticate (browser will open)
- Create 6 sheets with proper columns in your Google Sheet
- Save authentication token for future use

## Using NOVA II

### Activate Environment (Each Session)

Always activate the virtual environment first:

```bash
cd "/Users/benpoovaviranon/Desktop/Ben/AI & Automation/Ben's Agentic Automation"
source venv/bin/activate
```

---

## Knowledge Base Features

### Store Information

```bash
# Store a note
python execution/kb_store.py "Meeting Notes" "Discussed Q1 goals with team" --category "Notes"

# Store a lesson learned
python execution/kb_store.py "Pricing Strategy" "Must set clear prices upfront to avoid negotiations" --category "Lessons" --tags "business,pricing"

# Store business information
python execution/kb_store.py "Marketing Plan" "Focus on TikTok and Instagram" --category "Business" --tags "marketing,social"

# Store customer info
python execution/kb_store.py "Customer ABC" "Works at XYZ Corp, prefers email contact" --category "Customers" --tags "client"

# Auto-categorize (will go to 'Other' if uncertain)
python execution/kb_store.py "Random Idea" "Some interesting thought"
```

**Categories:** Notes, Lessons, Business, Customers, Other

### Search/Retrieve Information

```bash
# Search across all sheets
python execution/kb_retrieve.py "pricing"

# Search in specific sheet
python execution/kb_retrieve.py "ABC" --sheet Customers

# Limit results
python execution/kb_retrieve.py "marketing" --limit 5

# Thai language search works too
python execution/kb_retrieve.py "บทเรียน"
```

---

## Goal Management Features

### Create a Goal

```bash
# Full goal with all details
python execution/goal_create.py "Create TikTok content" \
  --description "Record video about AI automation" \
  --due "2026-02-21" \
  --type "Content Creation" \
  --priority High \
  --reminder "Daily 9AM"

# Minimal goal (just name and due date required)
python execution/goal_create.py "Launch product" --due "2026-03-01"

# With Thai relative dates
python execution/goal_create.py "ทำคอนเทนต์" --due "สัปดาห์นี้" --reminder "ทุกวันเช้า"
```

**Priority Options:** High, Medium, Low  
**Reminder Examples:** "Daily 9AM", "Every 3 days", "Weekly Monday", "ทุกวันเช้า"

### Update a Goal

```bash
# Mark as completed
python execution/goal_update.py "GOAL-001" --status Completed

# Add progress notes
python execution/goal_update.py "Create TikTok" --notes "Recorded first video, needs editing"

# Update multiple fields
python execution/goal_update.py "GOAL-002" \
  --priority High \
  --due "2026-02-25" \
  --notes "Extended deadline due to new requirements"

# Change status
python execution/goal_update.py "Launch product" --status Paused
```

**Status Options:** Active, Completed, Paused, Cancelled

You can use either Goal ID (e.g., "GOAL-001") or part of the goal name.

### Check Reminders

```bash
# Just view reminders due now
python execution/goal_reminders.py

# View and update "Last Reminded" timestamps
python execution/goal_reminders.py --update
```

The script will show:
- All active goals that need reminders
- Days until due date (or overdue days)
- Latest progress update
- Priority and schedule

---

## Natural Language with AI Agent

When talking to the AI agent (me!), you can use natural language in Thai or English:

### Storing Knowledge

**You:** "บทเรียนที่ได้วันนี้ คือ ต้องตั้งราคาสินค้าให้ชัดเจนตั้งแต่แรก"

**NOVA:** *I'll extract the details and call `kb_store.py` to save it*

### Retrieving Knowledge

**You:** "ลูกค้า ABC บริษัทอะไรมาแล้วนะ?"

**NOVA:** *I'll search using `kb_retrieve.py` and tell you the answer*

### Creating Goals

**You:** "ตั้งเป้าหมายว่าจะสร้างคอนเทนต์ TikTok ให้ได้ภายในสัปดาห์นี้"

**NOVA:** *I'll ask for missing details, then call `goal_create.py`*

---

## Quick Reference

| Task | Command |
|------|---------|
| **Setup Sheets** | `python execution/initialize_sheets.py` |
| **Store Knowledge** | `python execution/kb_store.py "Title" "Content" --category CAT` |
| **Search Knowledge** | `python execution/kb_retrieve.py "query"` |
| **Create Goal** | `python execution/goal_create.py "Name" --due DATE` |
| **Update Goal** | `python execution/goal_update.py "ID" --status STATUS` |
| **Check Reminders** | `python execution/goal_reminders.py` |

## Tips

1. **Always activate venv first**: `source venv/bin/activate`
2. **Use Goal IDs for precision**: "GOAL-001" is faster than searching by name
3. **Tags help searching**: Add tags when storing knowledge for easier retrieval
4. **Update reminders regularly**: Run `goal_reminders.py --update` daily
5. **Natural language**: When talking to the AI agent, just speak naturally!

## Files Location

- **Google Sheet**: https://docs.google.com/spreadsheets/d/194ZhTkYYog4qHGALr0qSYuX4iXvuypELRKoVz_--3DA/edit
- **Scripts**: `execution/` directory
- **Directive**: `directives/nova_ii.md`

## Troubleshooting

### "credentials.json not found"
- Follow [GOOGLE_SETUP.md](file:///Users/benpoovaviranon/Desktop/Ben/AI%20&%20Automation/NOVA%20II/GOOGLE_SETUP.md) to download OAuth credentials

### "Permission denied"  
- Make sure you're authenticated with the Google account that owns the Sheet

### "Sheet not found"
- Run `initialize_sheets.py` first to create the schema

### Scripts won't run
- Make sure you activated venv: `source venv/bin/activate`
- Check all dependencies installed: `pip install -r requirements.txt`

---

**Ready to use NOVA II!** 🚀

For natural language interactions, just talk to the AI agent - I'll handle calling the right scripts for you!
