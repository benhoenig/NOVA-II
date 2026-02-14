import os
import sys
import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to sys.path to allow importing from execution/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import execution modules
try:
    from execution.llm_utils import LLMClient
except ImportError:
    LLMClient = None

# Initialize Flask App
app = Flask(__name__)

# Initialize LINE API
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('LINE_CHANNEL_SECRET')

if not channel_access_token or not channel_secret:
    print("Warning: LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET not set.")
    
line_bot_api = LineBotApi(channel_access_token or 'dummy')
handler = WebhookHandler(channel_secret or 'dummy')

# Logging
logging.basicConfig(level=logging.INFO)

@app.route("/callback", methods=['POST'])
def callback():
    # Get X-Line-Signature header value
    signature = request.headers.get('X-Line-Signature')

    # Get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # Handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text.strip()
    reply_text = process_command(user_message)
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

def process_command(message):
    """Process the user's message and return a reply."""
    
    # 1. Simple Commands
    if message.lower() == 'ping':
        return 'pong! NOVA II is online.'
        
    if message.lower() == 'help':
        return """🤖 NOVA II Commands:
- ping: Check status
- help: Show this menu
- (Natural Language): Simply chat to use AI features!
"""

    # 2. AI Interaction (Default)
    # Use LLM to interpret or chat
    if LLMClient:
        try:
            client = LLMClient()
            # Simple chat response for now
            response = client.generate_text(
                message, 
                system_prompt="You are NOVA II, a helpful AI assistant. Keep responses concise for LINE chat."
            )
            if response:
                return response
        except Exception as e:
            return f"Error using AI: {str(e)}"
            
    return "Sorry, I couldn't understand that."

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
