import os
import sys
import logging
import json
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import execution modules
try:
    from execution.llm_utils import LLMClient
    from execution.goal_create import create_goal
    from execution.supabase_db import save_chat_message, get_chat_history, delete_goal, search_knowledge, store_knowledge
    # Note: Other modules will be imported as needed or added here
except ImportError as e:
    print(f"Error importing modules: {e}")
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

# Store User ID (Simple file-based storage for MVP)
USER_ID_FILE = 'user_ids.json'

@app.route("/")
def index():
    return "NOVA II Bot is running!"

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
    user_id = event.source.user_id
    save_user_id(user_id)
    
    user_message = event.message.text.strip()
    reply_text = process_command(user_message, user_id)
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

def process_command(message, user_id):
    """Process message using LLM to determine intent."""
    
    if message.lower() == 'ping':
        return 'pong! NOVA II is online.'
        
    if not LLMClient:
        return "System Error: LLM Client not available."

    try:
        client = LLMClient()
        
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
        - Be conversational: Use friendly Thai (or English if Ben uses it).
        
        RECENT CONTEXT:
        {history_str}
        
        Available Intents:
        - CREATE_GOAL: User wants to create a new goal.
          Params: name, description, due_date (YYYY-MM-DD)
          
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
          
        - CHAT: General conversation or other requests.
          Params: response (your helpful reply)
        
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
            
            if not name:
                reply_text = "I need a name for the goal."
            else:
                # Use goal_create logic
                result = create_goal(name, description=desc, due_date=due, auto_breakdown=True)
                if result.get('success'):
                    reply_text = f"✅ เป้าหมาย '{name}' ถูกสร้างแล้ว!\n\n📅 กำหนดส่ง: {due or 'ไม่ระบุ'}\n📝 ผมได้สร้าง Action Plan เบื้องต้นให้แล้วครับ"
                else:
                    reply_text = f"❌ เกิดข้อผิดพลาดในการสร้างเป้าหมาย: {result.get('error')}"
            
        elif intent == 'VIEW_GOALS':
            from execution.goal_utils import get_active_goals
            goals = get_active_goals()
            
            if not goals:
                reply_text = "🔍 ไม่พบเป้าหมายที่กำลังดำเนินการอยู่ในขณะนี้ครับ"
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
                reply_text = "📅 ช่วงนี้ไม่มีภารกิจเร่งด่วนที่ต้องทำครับ พักผ่อนได้เต็มที่!"
            else:
                reply_text = "📅 รายการสิ่งที่ต้องทำ (Action Items):\n"
                for t in tasks:
                    goal_name = t.get('goals', {}).get('name', 'N/A')
                    reply_text += f"\n🔹 {t['name']}"
                    reply_text += f"\n   🎯 เป้าหมาย: {goal_name}"
                    if t.get('due_date'):
                        reply_text += f" (ส่ง: {t['due_date']})"
                    reply_text += f" [{t.get('status', 'Todo')}]"
                reply_text += "\n\nสู้ๆ ครับ! มีอะไรให้ผมช่วยอีกไหม?"
        
        elif intent == 'SEARCH_KNOWLEDGE':
            query = params.get('query')
            if not query:
                reply_text = "จะให้ผมช่วยค้นหาอะไรดีครับ? (เช่น ค้นหาเรื่องลูกค้า, ค้นหาไอเดีย)"
            else:
                search_results = search_knowledge(query)
                
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
                    reply_text = f"❌ ขออภัยครับ ผมไม่พบข้อมูลที่เกี่ยวข้องกับ '{query}' ในคลังสมองของคุณเลยครับ"
                else:
                    reply_text += "\n\nมีจุดไหนที่อยากให้ผมเจาะลึกเพิ่มไหมครับ?"
        
        elif intent == 'STORE_NOTE':
            title = params.get('title')
            content = params.get('content')
            category = params.get('category', 'Other')
            
            if not content:
                reply_text = "จะให้ผมบันทึกอะไรดีครับ? รบกวนแจ้งรายละเอียดหน่อยครับ"
            else:
                if not title:
                    title = content[:30] + "..." if len(content) > 30 else content
                
                note_data = {
                    "title": title,
                    "content": content,
                    "category": category
                }
                result = store_knowledge(note_data)
                if result:
                    reply_text = f"✅ บันทึกเรียบร้อยแล้วครับ! (ID: {result['id']})\n\n📂 หมวดหมู่: {category}\n📌 หัวข้อ: {title}"
                else:
                    reply_text = "❌ ขออภัยครับ เกิดข้อผิดพลาดในการบันทึกข้อมูล"
        
        elif intent == 'DELETE_GOAL':
            id_to_delete = params.get('goal_id')
            if not id_to_delete:
                reply_text = "รบกวนระบุ ID ของเป้าหมายที่ต้องการลบด้วยครับ (เช่น GOAL-001)"
            else:
                result = delete_goal(id_to_delete)
                if result:
                    reply_text = f"🗑️ ลบเป้าหมาย '{id_to_delete}' เรียบร้อยแล้วครับ"
                else:
                    reply_text = f"❌ ไม่พบเป้าหมาย ID '{id_to_delete}' ครับ"
        
        elif intent == 'CHAT':
            reply_text = params.get('response', "รับทราบครับ!")
             
        # 3. Save Assistant Response to History (Fail-safe)
        try:
            save_chat_message(user_id, "assistant", reply_text, intent)
        except Exception as e:
            app.logger.warning(f"Could not save assistant response to history: {e}")
        
        return reply_text

    except Exception as e:
        app.logger.error(f"Critical error in process_command: {e}")
        error_msg = f"ขออภัยครับ เกิดข้อผิดพลาดในระบบ: {str(e)}"
        
        # Safe save for error
        try:
            save_chat_message(user_id, "system_error", str(e))
        except:
            pass
            
        return error_msg

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
