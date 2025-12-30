import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
# We load these from Render Environment Variables for security
META_TOKEN = os.getenv("META_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GOOGLE_JSON_CREDS = os.getenv("GOOGLE_CREDENTIALS") # The entire JSON content of credentials.json

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