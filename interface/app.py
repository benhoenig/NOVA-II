import os
import sys
import logging
import json
import threading
import time
from datetime import datetime
from flask import Flask, request, abort, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to sys.path to ensure execution modules are found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Placeholder for LLMClient (will be imported lazily)
LLMClient = None

# Initialize Flask App
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'nova-ii-dev-secret-key-change-me')
app.permanent_session_lifetime = 86400  # 24 hours

# Register Dashboard Blueprint
from interface.dashboard_routes import dashboard
app.register_blueprint(dashboard)

# Initialize LINE API
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('LINE_CHANNEL_SECRET')
line_bot_api = LineBotApi(channel_access_token or 'dummy')
handler = WebhookHandler(channel_secret or 'dummy')

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Message De-duplication Cache
processed_message_ids = set()
cache_lock = threading.Lock()

# Warmup Thread
def warmup_modules():
    """Import heavy modules in background to speed up first request."""
    logger.info("🧵 Background warmup started...")
    try:
        import pandas
        import openai
        import anthropic
        from execution.llm_utils import LLMClient
        from execution.supabase_db import get_active_goals
        logger.info("✅ Background warmup complete.")
    except Exception as e:
        logger.warning(f"⚠️ Warmup partially failed: {e}")

# Start warmup
threading.Thread(target=warmup_modules, daemon=True).start()

# Store User ID (Simple file-based storage for MVP)
USER_ID_FILE = 'user_ids.json'

@app.route("/")
def index():
    return "NOVA II Bot is running!"

@app.route("/health")
def health():
    """Explicit health check for Render."""
    return jsonify({"status": "healthy", "timestamp": str(datetime.now())}), 200

def save_user_id(user_id):
    """Save User ID for push messages."""
    users = set()
    if os.path.exists(USER_ID_FILE):
        try:
            with open(USER_ID_FILE, 'r') as f:
                users = set(json.load(f))
        except:
            pass
    
    if user_id not in users:
        users.add(user_id)
        with open(USER_ID_FILE, 'w') as f:
            json.dump(list(users), f)
        print(f"Saved new user ID: {user_id}")

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    message_id = event.message.id
    user_id = event.source.user_id
    reply_token = event.reply_token
    user_message = event.message.text.strip()
    
    # 1. Check for duplicates (De-duplication)
    with cache_lock:
        if message_id in processed_message_ids:
            logger.info(f"⏭️ Skipping duplicate message: {message_id}")
            return
        processed_message_ids.add(message_id)
        # Keep cache size manageable (last 500 IDs)
        if len(processed_message_ids) > 500:
            processed_message_ids.pop()
    
    # 2. Save User ID
    save_user_id(user_id)
    
    # 3. Process in Background Thread
    def async_process():
        try:
            logger.info(f"🧵 Processing message {message_id} in background...")
            reply_text = process_command(user_message, user_id)
            
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text=reply_text)
            )
            logger.info(f"✅ Background processing complete for {message_id}")
        except Exception as e:
            logger.error(f"❌ Error in async_process: {e}")
            try:
                line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text="ขออภัยค่ะ โนว่าประมวลผลผิดพลาด รบกวนลองอีกครั้งนะคะ")
                )
            except:
                pass

    threading.Thread(target=async_process, daemon=True).start()
    logger.info(f"🚀 Started background thread for {message_id}. Returning 200 OK...")

def process_command(message, user_id):
    """Process message using LLM to determine intent."""
    global LLMClient
    
    # Lazy Imports
    from execution.supabase_db import (
        save_chat_message, get_chat_history, delete_goal, 
        search_knowledge, store_knowledge, update_knowledge, delete_task, update_task, get_task_by_name_partial,
        parse_supabase_error
    )
    from execution.llm_utils import LLMClient as ActualLLMClient
    from execution.goal_create import create_goal, breakdown_existing_goal
    
    if message.lower() == 'ping':
        return 'pong! NOVA II is online.'
        
    start_time = time.time()
    reply_text = "ขออภัยค่ะ โนว่าประมวลผลผิดพลาด"
    intent = "CHAT"
    
    try:
        logger.info(f"🤖 Starting AI Processing for message: {message[:20]}...")
        client = ActualLLMClient()
        
        # 0. Save User Message immediately for context (Fail-safe)
        try:
            save_chat_message(user_id, "user", message)
        except Exception as e:
            app.logger.warning(f"Could not save user message to history: {e}")
        
        # 0.1 Fetch Chat History
        history = []
        try:
            history = get_chat_history(user_id, limit=6)
        except Exception as e:
            app.logger.warning(f"Could not fetch chat history: {e}")
            
        history_str = "\n".join([f"{m['role']}: {m['message']}" for m in history])

        # 1. Intent Classification
        system_prompt = f"""
        You are NOVA II, Ben's personal AI Assistant. Your mission is to be his "Second Brain".
        You help Ben manage knowledge, track goals, and optimize his business/life.
        
        YOUR CORE PHILOSOPHY:
        - Be proactive: If Ben shares a fact, ask if he wants to save it.
        - Be reasoning-oriented: Don't just list data, evaluate it if asked.
        - Be conversational: Use friendly Thai (Female tone: use 'ค่ะ/คะ') or English.
        - Be knowledgeable: You have access to Supabase tables: 'knowledge_base', 'goals', 'tasks', and 'business_portfolio'.
        
        RECENT CONTEXT:
        {history_str}
        
        Available Intents:
        - CREATE_GOAL: User wants to create a new goal.
          Params: name, description, due_date (YYYY-MM-DD), response (a helpful Thai reply to clarify missing info)
          Note: This only creates the record. You MUST ask if they want a task breakdown afterwards.
          
        - CONFIRM_TASKS: User confirms they want the action plan/tasks for the LAST goal created.
          Params: goal_id (optional)
          
        - VIEW_GOALS: User wants to see their goals.
          Params: none
          
        - DAILY_BRIEF: User asks what to do today, this week, or their status.
          Params: none
          
        - SEARCH_KNOWLEDGE: User asks for information, facts, or looks up something.
          Params: query (search keywords)
          
        - STORE_NOTE: User explicitly wants to save information, lesson, or note.
          Params: title, content, category (Notes, Lessons, Business, Customers, Other)
          
        - UPDATE_NOTE: User wants to UPDATE/EDIT existing note content or consolidate information.
          Params: item_id (e.g., NOTE-123), title (optional), content (optional), category (optional)
          
        - UPDATE_KNOWLEDGE: User wants to update a knowledge entry (specifically category).
          Params: item_id (e.g., NOTE-123), category (Notes, Lessons, Business, Customers, Other)
          
        - DELETE_GOAL: User wants to delete a goal.
          Params: goal_id or name
          
        - UPDATE_TASK: User wants to change task status.
          Params: task_id or task_name, status
          
        - CHAT: General conversation.
          Params: response (your helpful reply)
        """
        
        response = client.generate_json(
            f"User Message: {message}\nCurrent Date: {datetime.now().strftime('%Y-%m-%d')}",
            system_prompt=system_prompt
        )
        
        if not response:
            return "Sorry, I couldn't process that request."
            
        intent = response.get('intent')
        params = response.get('params', {})
        
        # 2. Routing Logic
        if intent == 'CREATE_GOAL':
            name = params.get('name')
            desc = params.get('description', '')
            due = params.get('due_date')
            if not name:
                reply_text = params.get('response') or "ยินดีช่วยตั้งเป้าหมายค่ะ! อยากให้เป้าหมายนี้ชื่อว่าอะไรดีคะ?"
            else:
                result = create_goal(name, description=desc, due_date=due, auto_breakdown=False)
                if result.get('success'):
                    reply_text = f"✅ บันทึกเป้าหมาย '{name}' เรียบร้อยแล้วค่ะ!\n\n📅 กำหนดส่ง: {due or 'ไม่ระบุ'}\n\n**อยากให้โนว่าช่วยแตกเป็นรายการงานย่อย (Tasks) ให้เลยไหมคะ?**"
                else:
                    reply_text = f"❌ เกิดข้อผิดพลาดในการสร้างเป้าหมายค่ะ: {result.get('error')}"
            
        elif intent == 'CONFIRM_TASKS':
            from execution.goal_utils import get_active_goals
            goals = get_active_goals()
            if not goals:
                reply_text = "🔍 ไม่พบเป้าหมายล่าสุดค่ะ"
            else:
                last_goal = goals[0]
                result = breakdown_existing_goal(last_goal['id'])
                if result.get('success'):
                    reply_text = f"✨ โนว่าแตกงานย่อยให้ '{last_goal['name']}' เรียบร้อยแล้วค่ะ! {result.get('tasks_count')} รายการ"
                else:
                    reply_text = f"❌ ไม่สามารถแตกงานได้ค่ะ: {result.get('error')}"

        elif intent == 'UPDATE_KNOWLEDGE':
            item_id = params.get('item_id')
            new_cat = params.get('category')
            if not item_id or not new_cat:
                reply_text = "❌ รบกวนระบุรหัสโน้ตและหมวดหมู่ด้วยนะคะ"
            else:
                result = update_knowledge(item_id, {"category": new_cat})
                reply_text = f"✅ อัปเดตโน้ต '{item_id}' เป็นหมวด '{new_cat}' แล้วค่ะ!" if result else f"❌ ไม่พบโน้ตรหัส '{item_id}' ค่ะ"
        
        elif intent == 'SEARCH_KNOWLEDGE':
            query = params.get('query')
            if not query:
                reply_text = "จะให้ค้นหาอะไรดีคะ?"
            else:
                search_results = search_knowledge(query)
                reply_text = f"🔍 ผลการค้นหาสำหรับ '{query}':\n"
                # ... Simplified search response for brevty in overwrite ...
                found = False
                if search_results.get('knowledge'):
                    found = True
                    for k in search_results['knowledge']: reply_text += f"\n- {k['title']}"
                if not found: reply_text = f"❌ ไม่พบข้อมูลสำหรับ '{query}' ค่ะ"

        elif intent == 'STORE_NOTE':
            note_data = {"title": params.get('title', "Note"), "content": params.get('content'), "category": params.get('category', 'Notes')}
            result = store_knowledge(note_data)
            
            # Handle duplicate detection
            if result and result.get('duplicate_found'):
                existing_id = result.get('existing_id')
                existing_title = result.get('existing_title')
                reply_text = f"⚠️ พบโน้ตที่คล้ายกันอยู่แล้วค่ะ:\n\n📝 {existing_title} (ID: {existing_id})\n\nอยากให้อัปเดตโน้ตเดิมหรือสร้างใหม่อยู่ดีคะ?"
            elif result:
                reply_text = f"✅ บันทึกเรียบร้อยแล้วค่ะ! (ID: {result.get('id')})"
            else:
                reply_text = "❌ บันทึกไม่สำเร็จค่ะ"
        
        elif intent == 'UPDATE_NOTE':
            item_id = params.get('item_id')
            update_data = {}
            if params.get('title'): update_data['title'] = params['title']
            if params.get('content'): update_data['content'] = params['content']
            if params.get('category'): update_data['category'] = params['category']
            
            if not item_id:
                reply_text = "❌ รบกวนระบุรหัสโน้ตที่ต้องการแก้ไขด้วยนะคะ"
            else:
                result = update_knowledge(item_id, update_data)
                reply_text = f"✅ อัปเดตโน้ต '{item_id}' เรียบร้อยแล้วค่ะ!" if result else f"❌ ไม่พบโน้ตรหัส '{item_id}' ค่ะ"

        elif intent == 'VIEW_GOALS':
            from execution.goal_utils import get_active_goals
            goals = get_active_goals()
            reply_text = f"เป้าหมายตอนนี้ ({len(goals)}):\n" + "\n".join([f"📌 {g['id']}: {g['name']}" for g in goals]) if goals else "🔍 ไม่พบเป้าหมายค่ะ"

        elif intent == 'UPDATE_TASK':
            task_id = params.get('task_id')
            new_status = params.get('status', 'Done')
            result = update_task(task_id, {"status": new_status})
            reply_text = f"✅ อัปเดตงาน '{task_id}' เป็น '{new_status}' แล้วค่ะ" if result else "❌ อัปเดตไม่สำเร็จค่ะ"

        else: # CHAT
            reply_text = params.get('response', "รับทราบค่ะ!")

    except Exception as e:
        logger.error(f"❌ Error in process_command: {e}")
        err_code, msg = parse_supabase_error(e)
        reply_text = f"🚨 {msg}" if err_code == "SCHEMA_MISMATCH" else f"ขออภัยค่ะ เกิดข้อผิดพลาด: {msg}"
             
    finally:
        end_time = time.time()
        logger.info(f"✅ AI Processing complete in {end_time - start_time:.2f}s")
        try:
            save_chat_message(user_id, "assistant", reply_text, intent)
        except:
            pass
        return reply_text

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
