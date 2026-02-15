"""
NOVA II Dashboard - Flask Blueprint

Serves the web dashboard for viewing Knowledge Base, Goals & Tasks.
Uses PIN-based authentication stored in session cookies.
"""

import os
import functools
from flask import (
    Blueprint, render_template, request, redirect, 
    url_for, session, jsonify, abort
)
from datetime import datetime

dashboard = Blueprint(
    'dashboard', __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/dashboard/static'
)

# ─── Authentication ──────────────────────────────

def login_required(f):
    """Decorator to require PIN authentication."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('dashboard_authenticated'):
            return redirect(url_for('dashboard.login'))
        return f(*args, **kwargs)
    return decorated

@dashboard.route('/dashboard/login', methods=['GET', 'POST'])
def login():
    """PIN-based login page."""
    error = None
    if request.method == 'POST':
        pin = request.form.get('pin', '')
        correct_pin = os.getenv('DASHBOARD_PIN', '1234')
        if pin == correct_pin:
            session['dashboard_authenticated'] = True
            session.permanent = True
            return redirect(url_for('dashboard.home'))
        else:
            error = 'PIN ไม่ถูกต้องค่ะ'
    
    return render_template('login.html', error=error)

@dashboard.route('/dashboard/logout')
def logout():
    """Clear session and redirect to login."""
    session.clear()
    return redirect(url_for('dashboard.login'))

# ─── Dashboard Pages ─────────────────────────────

@dashboard.route('/dashboard')
@login_required
def home():
    """Main dashboard page (SPA)."""
    return render_template('dashboard.html')

# ─── API Endpoints ───────────────────────────────

@dashboard.route('/api/stats')
@login_required
def api_stats():
    """Summary statistics for dashboard cards."""
    from execution.supabase_db import supabase
    
    try:
        # Knowledge Base count
        kb = supabase.table("knowledge_base").select("id", count="exact").execute()
        kb_count = kb.count if hasattr(kb, 'count') and kb.count else len(kb.data)
        
        # Goals
        goals_active = supabase.table("goals").select("id", count="exact").eq("status", "Active").execute()
        active_count = goals_active.count if hasattr(goals_active, 'count') and goals_active.count else len(goals_active.data)
        
        goals_all = supabase.table("goals").select("id", count="exact").execute()
        total_goals = goals_all.count if hasattr(goals_all, 'count') and goals_all.count else len(goals_all.data)
        
        # Tasks
        tasks_all = supabase.table("tasks").select("id, status").execute()
        total_tasks = len(tasks_all.data)
        done_tasks = sum(1 for t in tasks_all.data if t.get('status') == 'Done')
        
        return jsonify({
            'success': True,
            'stats': {
                'active_goals': active_count,
                'total_goals': total_goals,
                'total_tasks': total_tasks,
                'done_tasks': done_tasks,
                'kb_entries': kb_count,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard.route('/api/goals')
@login_required
def api_goals():
    """Goals with linked tasks."""
    from execution.supabase_db import supabase
    
    try:
        # Fetch goals ordered by status (Active first) then due_date
        goals = supabase.table("goals") \
            .select("*") \
            .order("status", desc=False) \
            .order("due_date", desc=False) \
            .execute()
        
        # For each goal, fetch tasks
        result = []
        for goal in goals.data:
            tasks = supabase.table("tasks") \
                .select("*") \
                .eq("goal_id", goal['id']) \
                .order("created_at", desc=False) \
                .execute()
            
            total = len(tasks.data)
            done = sum(1 for t in tasks.data if t.get('status') == 'Done')
            
            # Calculate urgency
            urgency = 'normal'
            if goal.get('due_date'):
                try:
                    due = datetime.strptime(goal['due_date'], '%Y-%m-%d').date()
                    days_left = (due - datetime.now().date()).days
                    if days_left < 0:
                        urgency = 'overdue'
                    elif days_left <= 3:
                        urgency = 'urgent'
                    elif days_left <= 7:
                        urgency = 'warning'
                except:
                    pass
            
            result.append({
                **goal,
                'tasks': tasks.data,
                'tasks_total': total,
                'tasks_done': done,
                'progress': round((done / total * 100) if total > 0 else 0),
                'urgency': urgency
            })
        
        return jsonify({'success': True, 'goals': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard.route('/api/kb')
@login_required
def api_kb():
    """Knowledge base entries with optional category filter."""
    from execution.supabase_db import supabase
    
    try:
        category = request.args.get('category')
        search = request.args.get('search')
        
        query = supabase.table("knowledge_base") \
            .select("*") \
            .order("created_at", desc=True)
        
        if category and category != 'All':
            query = query.eq("category", category)
        
        if search:
            query = query.or_(f"title.ilike.%{search}%,content.ilike.%{search}%")
        
        result = query.limit(50).execute()
        
        # Get unique categories for filter
        all_cats = supabase.table("knowledge_base").select("category").execute()
        categories = sorted(set(item['category'] for item in all_cats.data if item.get('category')))
        
        return jsonify({
            'success': True, 
            'entries': result.data,
            'categories': categories
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ─── Chat API Endpoints ─────────────────────────

@dashboard.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    """Send a message to NOVA and get a response."""
    from interface.app import process_command
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON'}), 400
    
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'success': False, 'error': 'Empty message'}), 400
    
    try:
        user_id = 'dashboard-user'
        reply = process_command(message, user_id)
        return jsonify({
            'success': True,
            'reply': reply,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard.route('/api/chat/history')
@login_required
def api_chat_history():
    """Load chat history for dashboard user."""
    from execution.supabase_db import get_chat_history
    
    try:
        messages = get_chat_history('dashboard-user', limit=50)
        return jsonify({'success': True, 'messages': messages})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ─── Calendar API Endpoint ───────────────────────

@dashboard.route('/api/calendar')
@login_required
def api_calendar():
    """Get upcoming calendar events."""
    from execution.google_calendar import list_events
    
    try:
        days = int(request.args.get('days', 7))
        events = list_events(days=days)
        return jsonify({'success': True, 'events': events})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

