# app.py
import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from services import get_google_sheet_contacts, send_whatsapp_template
from dotenv import load_dotenv
from services import get_google_sheet_contacts, send_whatsapp_template, get_groq_response, send_whatsapp_text, send_brevo_email

load_dotenv()
app = Flask(__name__)
# Allow Vercel frontend to talk to this backend
CORS(app, resources={r"/*": {"origins": "*"}})

# Security: The password required to fire the blast
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "default_secret") 

@app.route("/")
def home():
    return jsonify({"status": "Backend is running", "platform": "Render"}), 200

@app.route("/api/send-blast", methods=["POST"])
def send_blast():
    data = request.json
    
    # 1. INPUTS
    user_password = data.get("password")
    message_body = data.get("message")
    image_url = data.get("image_url")
    
    # NEW: Checkbox States (Default to False if missing)
    send_whatsapp_flag = data.get("send_whatsapp", False)
    send_email_flag = data.get("send_email", False)

    sheet_url = os.getenv("DEFAULT_SHEET_URL")
    
    if not user_password or not message_body:
        return jsonify({"error": "Missing inputs"}), 400
    if user_password != ADMIN_PASSWORD:
        return jsonify({"error": "Wrong Password"}), 403
    
    # Validation: User must select at least one channel
    if not send_whatsapp_flag and not send_email_flag:
        return jsonify({"error": "Please select at least one sending method (WhatsApp or Email)."}), 400

    # 2. GET CONTACTS
    contacts = get_google_sheet_contacts(sheet_url)
    if not contacts:
        return jsonify({"error": "Sheet error or empty"}), 500

    # 3. SEND LOOP
    stats = {"whatsapp_sent": 0, "whatsapp_fail": 0, "email_sent": 0, "email_fail": 0}
    
    print(f"Starting blast... WA: {send_whatsapp_flag}, Email: {send_email_flag}")
    
    for row in contacts:
        # --- CLEAN NAME ---
        # The service layer ensures the key is always 'Name' now
        raw_name = str(row.get('Name', 'Valued Customer')).strip()
        clean_name = raw_name.split('-')[0].split('|')[0].strip() or "Valued Customer"

        # --- OPTION 1: WHATSAPP ---
        if send_whatsapp_flag:
            # The service layer ensures the key is always 'Phone' now
            raw_phone = str(row.get('Phone', '')).strip()
            phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if phone.startswith('0'): phone = phone[1:]
            
            # Send only if valid mobile
            if phone and not phone.startswith('011') and len(phone) >= 10:
                if not phone.startswith('91') and not phone.startswith('+'):
                    phone = "91" + phone
                
                status, _ = send_whatsapp_template(phone, clean_name, message_body, image_url)
                if status in [200, 201]:
                    stats["whatsapp_sent"] += 1
                else:
                    stats["whatsapp_fail"] += 1

        # --- OPTION 2: EMAIL ---
        if send_email_flag:
            # The service layer ensures the key is always 'Email ids' now
            email = str(row.get('Email ids', '')).strip()
            
            # Handle multiple emails
            if ',' in email: email = email.split(',')[0].strip()
            if ' ' in email: email = email.split(' ')[0].strip()

            if email and '@' in email:
                subject = f"Update for {clean_name}"
                
                # CHANGED: Call send_brevo_email instead of send_gmail
                if send_brevo_email(email, subject, message_body, clean_name):
                    stats["email_sent"] += 1
                else:
                    stats["email_fail"] += 1
    
    return jsonify({
        "status": "completed",
        "total_rows": len(contacts),
        "stats": stats
    }), 200

# Webhook for Replies (We will build this out later)
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # 1. VERIFICATION (Meta checks if you exist)
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        # Check if the token matches your Render Environment Variable
        if mode == "subscribe" and token == os.getenv("VERIFY_TOKEN"):
            return challenge, 200
        return "Forbidden", 403

    # 2. INCOMING MESSAGES (User sent something)
    if request.method == "POST":
        data = request.get_json()
        
        # Print for debugging in Render logs
        print("Incoming Webhook:", data)

        try:
            # Parse the deeply nested JSON from Meta
            if data.get("entry") and data["entry"][0].get("changes"):
                change = data["entry"][0]["changes"][0]["value"]
                
                # Check if it's a message (and not a status update like 'read' or 'delivered')
                if "messages" in change:
                    message_data = change["messages"][0]
                    phone_no = message_data["from"]
                    
                    # We only handle text messages for now
                    if message_data["type"] == "text":
                        user_text = message_data["text"]["body"]
                        
                        # 1. Ask Groq for a reply
                        ai_reply = get_groq_response(user_text)
                        
                        # 2. Send the reply back to WhatsApp
                        send_whatsapp_text(phone_no, ai_reply)

        except Exception as e:
            print(f"Webhook Error: {e}")

        # Always return 200 OK to Meta, otherwise they will stop sending messages
        return jsonify({"status": "received"}), 200

if __name__ == "__main__":
    app.run(debug=True)