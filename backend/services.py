import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
# --- CONFIGURATION ---

# We load these from Render Environment Variables for security
META_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GOOGLE_JSON_CREDS = os.getenv("GOOGLE_CREDENTIALS") # The entire JSON content of credentials.json
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


groq_client = Groq(api_key=GROQ_API_KEY)

def get_google_sheet_contacts(sheet_url):
    """
    Connects to Google Sheets and returns a list of contacts.
    Expected Columns: 'Name', 'Phone'
    """
    try:
        # 1. Try to get credentials from Environment (Render way)
        json_creds = os.getenv("GOOGLE_CREDENTIALS")
        
        # 2. If ENV is empty, try looking for a local file (Local Windows way)
        if not json_creds:
            if os.path.exists("credentials.json"):
                print("⚠️ Using local credentials.json file")
                with open("credentials.json", "r") as f:
                    json_creds = f.read()
            else:
                print("❌ No credentials found in ENV or local file!")
                return None

        # Parse the string into a dictionary
        creds_dict = json.loads(json_creds)
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Open the sheet by URL (easier than name)
        sheet = client.open_by_url(sheet_url).sheet1
        
        # Get all records as a list of dictionaries
        # Example: [{'Name': 'Shahid', 'Phone': '919876543210'}, ...]
        return sheet.get_all_records()
    except Exception as e:
        print(f"Google Sheet Error: {e}")
        return None

def send_whatsapp_template(to_number, custom_message):
    """
    Sends a 'flexible' template message where the variable is your custom text.
    """
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # We use a template named 'generic_alert' (You must create this in Meta Dashboard)
    # It should have body text like: "Update: {{1}}"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": "generic_alert", 
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        # This injects your custom message into the template
                        {"type": "text", "text": custom_message} 
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code, response.json()
    except Exception as e:
        return 500, str(e)
    
def get_groq_response(user_text):
    """
    Sends the user's message to Llama 3 via Groq and gets a smart reply.
    """
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful customer support assistant for a business. Keep replies concise, professional, and friendly."
                },
                {
                    "role": "user",
                    "content": user_text,
                }
            ],
            # 👇 THIS IS THE ONLY LINE YOU CHANGE
            model="llama-3.3-70b-versatile", 
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Groq Error: {e}")
        return "I'm having trouble thinking right now. Please try again later."

def send_whatsapp_text(to_number, text_body):
    """
    Sends a standard text reply (Allowed only within 24h of user message).
    """
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text_body}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code
    except Exception as e:
        print(f"Send Error: {e}")
        return 500