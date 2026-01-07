import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from services import get_google_sheet_contacts, send_whatsapp_template
from dotenv import load_dotenv
from services import get_google_sheet_contacts, send_whatsapp_template, get_groq_response, send_whatsapp_text

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
    sheet_url = os.getenv("DEFAULT_SHEET_URL")
    
    if not user_password or not message_body:
        return jsonify({"error": "Missing inputs"}), 400
    if user_password != ADMIN_PASSWORD:
        return jsonify({"error": "Wrong Password"}), 403

    # 2. GET CONTACTS
    contacts = get_google_sheet_contacts(sheet_url)
    if not contacts:
        return jsonify({"error": "Sheet error or empty"}), 500

    # 3. SEND LOOP
    success_count = 0
    fail_count = 0
    skipped_count = 0
    
    print(f"Starting blast to {len(contacts)} rows...")
    
    for row in contacts:
        # --- A. SMART PHONE EXTRACTION ---
        # Try 'Phone' column first, if empty/missing, try 'UsdlK' (from your scraper)
        raw_phone = str(row.get('Phone', '') or row.get('UsdlK', '')).strip()
        
        # CLEANING STEPS:
        # 1. Remove spaces, dashes, and parenthesis
        phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # 2. Remove leading '0' (e.g., 098100 -> 98100)
        if phone.startswith('0'):
            phone = phone[1:]
            
        # 3. Skip empty numbers or Landlines (011...) if you only want mobiles
        # Note: 011 is Delhi landline. WhatsApp API often fails on unverified landlines.
        if not phone or phone.startswith('011') or len(phone) < 10:
            skipped_count += 1
            continue

        # 4. Add Country Code (91) if missing
        if not phone.startswith('91') and not phone.startswith('+'):
            phone = "91" + phone
        
        # --- B. SMART NAME CLEANING ---
        # Get raw name
        raw_name = str(row.get('Name', 'Valued Customer')).strip()
        
        # Truncate long SEO names. 
        # Example: "Dr. Gupta's Clinic - Best Dentist in Delhi" -> "Dr. Gupta's Clinic"
        # We split by '-' or '|' and take the first part
        clean_name = raw_name.split('-')[0].split('|')[0].strip()
        
        # Fallback if name becomes empty after cleaning
        if not clean_name:
            clean_name = "Valued Customer"

        # --- C. SEND MESSAGE ---
        if phone:
            # Pass the CLEANED name and phone
            status, _ = send_whatsapp_template(phone, clean_name, message_body, image_url)
            
            if status in [200, 201]:
                success_count += 1
            else:
                fail_count += 1
    
    return jsonify({
        "status": "completed",
        "total_rows": len(contacts),
        "successful": success_count,
        "failed": fail_count,
        "skipped_invalid": skipped_count
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