import os
import json
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load local .env if you have one
load_dotenv()

def test_gmail_sending():
    print("--- 📧 STARTING GMAIL TEST ---")
    
    # 🎯 TARGET EMAIL
    TO_EMAIL = "shahid3332210@gmail.com"
    
    # 1. LOAD TOKEN
    # First, try getting it from the Environment Variable (Simulating Render)
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    
    # If not in Env, look for the local file (Simulating Local Dev)
    if not token_json:
        print("⚠️  Env var 'GMAIL_TOKEN_JSON' is empty.")
        print("📂 Checking for local 'token_gmail.json' file instead...")
        
        if os.path.exists("token_gmail.json"):
            with open("token_gmail.json", "r") as f:
                token_json = f.read()
            print("✅ Found local 'token_gmail.json'. Using it.")
        else:
            print("❌ ERROR: No token found! set GMAIL_TOKEN_JSON in env OR have token_gmail.json in this folder.")
            return

    try:
        # 2. AUTHENTICATE
        # Parse the JSON string into credentials
        creds_data = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(creds_data)
        
        # Build the Gmail Service
        service = build('gmail', 'v1', credentials=creds)
        print("✅ Authenticated with Google successfully.")

        # 3. CREATE EMAIL
        subject = "Test: Bot Connection Success"
        body_text = "Hello! If you are reading this, the Python Bot has successfully connected to your services@shoutotb.com Gmail account."
        
        message = MIMEText(body_text)
        message['to'] = TO_EMAIL
        message['subject'] = subject
        
        # Encode (Google specific requirement)
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': raw_message}

        # 4. SEND
        print(f"🚀 Sending email to {TO_EMAIL}...")
        sent_msg = service.users().messages().send(userId="me", body=create_message).execute()
        
        print(f"✅ SUCCESS! Email Sent.")
        print(f"Message ID: {sent_msg['id']}")
        
    except Exception as e:
        print(f"\n❌ FAILED to send email.")
        print(f"Error Details: {e}")

if __name__ == "__main__":
    test_gmail_sending()