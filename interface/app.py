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
        
        # 1. Intent Classification
        system_prompt = """
        You are NOVA II, an intelligent assistant. 
        Analyze the user's message and determine the INTENT and PARAMETERS.
        
        Available Intents:
        - CREATE_GOAL: User wants to create a new goal.
          Params: name, description, due_date (YYYY-MM-DD)
          
        - VIEW_GOALS: User wants to see their goals.
          Params: none
          
        - DAILY_BRIEF: User asks what to do today.
          Params: none
          
        - CHAT: General conversation or other requests.
          Params: response (your helpful reply)
        
        Return a JSON object:
        {
            "intent": "INTENT_NAME",
            "params": { ... }
        }
        """
        
        response = client.generate_json(
            f"User Message: {message}\nCurrent Date: {datetime.now().strftime('%Y-%m-%d')}",
            system_prompt=system_prompt
        )
        
        if not response:
            return "Sorry, I couldn't process that request."
            
        intent = response.get('intent')
        params = response.get('params', {})
        
        # 2. Route to Function
        if intent == 'CREATE_GOAL':
            name = params.get('name')
            desc = params.get('description', '')
            due = params.get('due_date')
            
            if not name:
                return "I need a name for the goal."
            
            # Use goal_create logic
            result = create_goal(name, description=desc, due_date=due, auto_breakdown=True)
            
            if result.get('success'):
                return f"✅ เป้าหมาย '{name}' ถูกสร้างแล้ว!\n\n📅 กำหนดส่ง: {due or 'ไม่ระบุ'}\n📝 ผมได้สร้าง Action Plan เบื้องต้นให้แล้วครับ"
            else:
                return f"❌ เกิดข้อผิดพลาดในการสร้างเป้าหมาย: {result.get('error')}"
            
        elif intent == 'VIEW_GOALS':
            from execution.goal_utils import get_active_goals
            goals = get_active_goals()
            
            if not goals:
                return "🔍 ไม่พบเป้าหมายที่กำลังดำเนินการอยู่ในขณะนี้ครับ"
            
            reply = f"รายการเป้าหมายของคุณ ({len(goals)}):\n"
            for g in goals:
                reply += f"\n📌 {g['name']}"
                if g['due_date']:
                    reply += f" (Due: {g['due_date']})"
                if g['priority']:
                    reply += f" [{g['priority']}]"
            
            return reply
             
        elif intent == 'DAILY_BRIEF':
            from execution.goal_utils import get_daily_tasks
            goals = get_daily_tasks()
            
            if not goals:
                return "📅 วันนี้ไม่มีภารกิจเร่งด่วนครับ พักผ่อนได้เต็มที่!"
            
            reply = "📅 สรุปภารกิจสำหรับวันนี้:\n"
            for g in goals:
                reply += f"\n🎯 {g['name']}"
                if g['due_date']:
                    reply += f" - กำหนดส่ง {g['due_date']}"
            
            reply += "\n\nสู้ๆ ครับ! มีอะไรให้ผมช่วยอีกไหม?"
            return reply
             
        elif intent == 'CHAT':
            return params.get('response', "รับทราบครับ!")
            
        else:
            return "Unknown intent."

    except Exception as e:
        print(f"Error: {e}")
        return f"Error processing command: {str(e)}"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
