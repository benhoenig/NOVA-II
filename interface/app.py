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

# Load environment variables
load_dotenv()

# Add project root to sys.path to ensure execution modules are found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Placeholder for LLMClient (will be imported lazily)
LLMClient = None

# Initialize Flask App
app = Flask(__name__)

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
            # Optional: Send error message back if token is still valid
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
        search_knowledge, store_knowledge, delete_task, update_task, get_task_by_name_partial
    )
    from execution.llm_utils import LLMClient as ActualLLMClient
    from execution.goal_create import create_goal, breakdown_existing_goal
    
    if message.lower() == 'ping':
        return 'pong! NOVA II is online.'
        
    try:
        logger.info(f"🤖 Starting AI Processing for message: {message[:20]}...")
        start_time = time.time()
        client = ActualLLMClient()
        
        # 0. Save User Message immediately for context (Fail-safe)
        try:
            save_chat_message(user_id, "user", message)
        except Exception as e:
            app.logger.warning(f"Could not save user message to history: {e}")
        
        # 0.1 Fetch Chat History (including the current message)
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
          
        - CONFIRM_TASKS: User says "Yes", "ตกลง", "ช่วยแตกงานหน่อย" or confirms they want the action plan/tasks for the LAST goal created.
          Params: goal_id (optional, if mentioned)
          
        - VIEW_GOALS: User wants to see their goals.
          Params: none
          
        - DAILY_BRIEF: User asks what to do today, this week, or their status.
          Params: none
          
        - SEARCH_KNOWLEDGE: User asks for information, facts, or looks up something from their records (customers, notes, business).
          Params: query (search keywords)
          
        - STORE_NOTE: User explicitly wants to save or record some information, lesson, or note.
          Params: title, content, category (Notes, Lessons, Business, Customers, Other)
          
        - DELETE_GOAL: User wants to delete an existing goal by its ID or name.
          Params: goal_id (e.g., GOAL-001) or name
          
        - DELETE_TASK: User wants to delete a specific task/action item.
          Params: task_id or task_name
          
        - UPDATE_TASK: User wants to change task status (e.g. to 'Done', 'In Progress').
          Params: task_id or task_name, status
          
        - CHAT: General conversation.
          Params: response (your helpful reply)
          
        SPECIAL PROTOCOL:
        If Ben asks for a FEATURE or CAPABILITY that is NOT in the list above:
        1. Set intent to 'CHAT'
        2. Set response to: "ขออภัยค่ะ ตอนนี้โนว่ายังทำ [สิ่งที่ขอ] ไม่ได้ค่ะ จะให้โนว่าจด Note ประเด็นนี้ไว้ใน Knowledge Base (คลังบทเรียน) เพื่อเตรียมให้คุณ Ben แก้ไขปรับปรุงโนว่าใน IDE ทีหลังไหมคะ?"
        
        Return a JSON object:
        {{
            "intent": "INTENT_NAME",
            "params": {{ ... }}
        }}
        """
        
        response = client.generate_json(
            f"User Message: {message}\nCurrent Date: {datetime.now().strftime('%Y-%m-%d')}",
            system_prompt=system_prompt
        )
        
        if not response:
            return "Sorry, I couldn't process that request."
            
        intent = response.get('intent')
        params = response.get('params', {})
        reply_text = "I'm not sure how to help with that yet."
        
        # 2. Route to Function
        if intent == 'CREATE_GOAL':
            name = params.get('name')
            desc = params.get('description', '')
            due = params.get('due_date')
            llm_response = params.get('response')
            
            if not name:
                reply_text = llm_response or "ยินดีช่วยตั้งเป้าหมายค่ะ! อยากให้เป้าหมายนี้ชื่อว่าอะไรดีคะ?"
            else:
                # Use goal_create logic - Default to False for auto_breakdown
                logger.info(f"🎯 Creating goal: {name} (Auto-breakdown: False)")
                result = create_goal(name, description=desc, due_date=due, auto_breakdown=False)
                logger.info(f"✅ Goal creation result: {result.get('success')}")
                if result.get('success'):
                    goal_id = result.get('goal_id')
                    reply_text = f"✅ บันทึกเป้าหมาย '{name}' เรียบร้อยแล้วค่ะ!\n\n📅 กำหนดส่ง: {due or 'ไม่ระบุ'}\n\n**อยากให้โนว่าช่วยแตกเป็นรายการงานย่อย (Tasks) ให้เลยไหมคะ?** (พิมพ์ 'ใช่' หรือ 'ตกลง' ได้เลยค่ะ)"
                else:
                    reply_text = f"❌ เกิดข้อผิดพลาดในการสร้างเป้าหมายค่ะ: {result.get('error')}"
            
        elif intent == 'CONFIRM_TASKS':
            from execution.goal_utils import get_active_goals
            goals = get_active_goals()
            
            if not goals:
                reply_text = "🔍 ไม่พบเป้าหมายล่าสุดที่กำลังดำเนินการอยู่ค่ะ รบกวนสร้างเป้าหมายก่อนนะคะ"
            else:
                # Take the most recent goal
                last_goal = goals[0] # Assumes ordered by created_at desc
                goal_id = last_goal['id']
                goal_name = last_goal['name']
                
                logger.info(f"🧠 Breaking down goal: {goal_name} ({goal_id})")
                result = breakdown_existing_goal(goal_id)
                
                if result.get('success'):
                    reply_text = f"✨ โนว่าแตกรายการงานย่อยให้เป้าหมาย '{goal_name}' เรียบร้อยแล้วค่ะ! {result.get('tasks_count')} รายการ\n\nสามารถพิมพ์ 'เช็คงาน' เพื่อดูรายละเอียดได้นะคะ"
                else:
                    reply_text = f"❌ ขออภัยค่ะ โนว่าไม่สามารถแตกรายการงานได้ในขณะนี้: {result.get('error')}"
            
        elif intent == 'VIEW_GOALS':
            from execution.goal_utils import get_active_goals
            goals = get_active_goals()
            
            if not goals:
                reply_text = "🔍 ไม่พบเป้าหมายที่กำลังดำเนินการอยู่ในขณะนี้ค่ะ"
            else:
                reply_text = f"รายการเป้าหมายของคุณ ({len(goals)}):\n"
                for g in goals:
                    reply_text += f"\n📌 {g['id']}: {g['name']}"
                    if g['due_date']:
                        reply_text += f" (Due: {g['due_date']})"
                    if g.get('priority'):
                        reply_text += f" [{g['priority']}]"
            
        elif intent == 'DAILY_BRIEF':
            from execution.goal_utils import get_daily_tasks
            tasks = get_daily_tasks()
            
            if not tasks:
                reply_text = "📅 ช่วงนี้ไม่มีภารกิจเร่งด่วนที่ต้องทำค่ะ พักผ่อนได้เต็มที่!"
            else:
                reply_text = "📅 รายการสิ่งที่ต้องทำ (Action Items):\n"
                for t in tasks:
                    goal_name = t.get('goals', {}).get('name', 'N/A')
                    reply_text += f"\n🔹 {t['name']}"
                    reply_text += f"\n   🎯 เป้าหมาย: {goal_name}"
                    if t.get('due_date'):
                        reply_text += f" (ส่ง: {t['due_date']})"
                    reply_text += f" [{t.get('status', 'Todo')}]"
                reply_text += "\n\nสู้ๆ ค่ะ! มีอะไรให้โนว่าช่วยอีกไหมคะ?"
        
        elif intent == 'SEARCH_KNOWLEDGE':
            query = params.get('query')
            if not query:
                reply_text = "จะให้โนว่าช่วยค้นหาอะไรดีคะ? (เช่น ค้นหาเรื่องลูกค้า, ค้นหาไอเดีย)"
            else:
                logger.info(f"🔍 Searching knowledge for: {query}")
                search_results = search_knowledge(query)
                logger.info("✅ Search complete")
                
                reply_text = f"🔍 ผลการค้นหาสำหรับ '{query}':\n"
                found_anything = False
                
                if search_results.get('knowledge'):
                    found_anything = True
                    reply_text += "\n📝 **บันทึกความรู้:**"
                    for k in search_results['knowledge']:
                        reply_text += f"\n- {k['title']}: {k['content'][:100]}..."
                
                if search_results.get('goals'):
                    found_anything = True
                    reply_text += "\n🎯 **เป้าหมาย:**"
                    for g in search_results['goals']:
                        reply_text += f"\n- {g['id']}: {g['name']} ({g['status']})"
                        
                if search_results.get('business'):
                    found_anything = True
                    reply_text += "\n💼 **ธุรกิจ:**"
                    for b in search_results['business']:
                        reply_text += f"\n- {b['name']}: {b['description'][:100]}..."
                
                if not found_anything:
                    reply_text = f"❌ ขออภัยค่ะ โนว่าไม่พบข้อมูลที่เกี่ยวข้องกับ '{query}' ในคลังสมองของคุณเลยค่ะ"
                else:
                    reply_text += "\n\nมีจุดไหนที่อยากให้โนว่าเจาะลึกเพิ่มไหมคะ?"
        
        elif intent == 'STORE_NOTE':
            title = params.get('title')
            content = params.get('content')
            category = params.get('category', 'Other')
            
            if not content:
                reply_text = "จะให้โนว่าบันทึกอะไรดีคะ? รบกวนแจ้งรายละเอียดหน่อยค่ะ"
            else:
                if not title:
                    title = content[:30] + "..." if len(content) > 30 else content
                
                note_data = {
                    "title": title,
                    "content": content,
                    "category": category
                }
                logger.info(f"💾 Storing note: {title}")
                result = store_knowledge(note_data)
                logger.info(f"✅ Store result: {result['id'] if result else 'Failed'}")
                if result:
                    reply_text = f"✅ บันทึกเรียบร้อยแล้วค่ะ! (ID: {result['id']})\n\n📂 หมวดหมู่: {category}\n📌 หัวข้อ: {title}"
                else:
                    reply_text = "❌ ขออภัยค่ะ เกิดข้อผิดพลาดในการบันทึกข้อมูล"
        
        elif intent == 'DELETE_GOAL':
            id_to_delete = params.get('goal_id')
            if not id_to_delete:
                reply_text = "รบกวนระบุ ID ของเป้าหมายที่ต้องการลบด้วยค่ะ (เช่น GOAL-001)"
            else:
                result = delete_goal(id_to_delete)
                if result:
                    reply_text = f"🗑️ ลบเป้าหมาย '{id_to_delete}' เรียบร้อยแล้วค่ะ"
                else:
                    reply_text = f"❌ ไม่พบเป้าหมาย ID '{id_to_delete}' ค่ะ"
        
        elif intent == 'DELETE_TASK':
            task_id = params.get('task_id')
            task_name = params.get('task_name')
            
            if not task_id and task_name:
                # Try to find task_id by name
                tasks = get_task_by_name_partial(task_name)
                if tasks:
                    task_id = tasks[0]['id']
            
            if not task_id:
                reply_text = "รบกวนระบุ ID หรือชื่อของงานที่ต้องการลบด้วยค่ะ"
            else:
                result = delete_task(task_id)
                if result:
                    reply_text = f"🗑️ ลบงาน ID '{task_id}' เรียบร้อยแล้วค่ะ"
                else:
                    reply_text = f"❌ ไม่พบงาน ID '{task_id}' หรือเกิดข้อผิดพลาดค่ะ"

        elif intent == 'UPDATE_TASK':
            task_id = params.get('task_id')
            task_name = params.get('task_name')
            new_status = params.get('status', 'Done')
            
            if not task_id and task_name:
                tasks = get_task_by_name_partial(task_name)
                if tasks:
                    task_id = tasks[0]['id']
            
            if not task_id:
                reply_text = "รบกวนระบุงานที่ต้องการอัปเดตสถานะค่ะ"
            else:
                result = update_task(task_id, {"status": new_status})
                if result:
                    reply_text = f"✅ อัปเดตงาน '{task_id}' เป็นสถานะ '{new_status}' เรียบร้อยแล้วค่ะ"
                else:
                    reply_text = f"❌ ไม่สามารถอัปเดตสถานะงานได้ค่ะ"
        
        elif intent == 'CHAT':
            reply_text = params.get('response', "รับทราบค่ะ!")
             
        end_time = time.time()
        logger.info(f"✅ AI Processing complete in {end_time - start_time:.2f}s")
             
        # 3. Save Assistant Response to History (Fail-safe)
        try:
            save_chat_message(user_id, "assistant", reply_text, intent)
        except Exception as e:
            app.logger.warning(f"Could not save assistant response to history: {e}")
        
        return reply_text

    except Exception as e:
        app.logger.error(f"Critical error in process_command: {e}")
        error_msg = f"ขออภัยค่ะ เกิดข้อผิดพลาดในระบบ: {str(e)}"
        
        # Safe save for error
        try:
            save_chat_message(user_id, "system_error", str(e))
        except:
            pass
            
        return error_msg

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
