import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from services import get_google_sheet_contacts, send_whatsapp_template

app = Flask(__name__)
# Allow Vercel frontend to talk to this backend
CORS(app) 

# Security: The password required to fire the blast
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "default_secret") 

@app.route("/")
def home():
    return jsonify({"status": "Backend is running", "platform": "Render"}), 200

@app.route("/api/send-blast", methods=["POST"])
def send_blast():
    data = request.json
    
    # 1. INPUT VALIDATION
    user_password = data.get("password")
    message_body = data.get("message")
    
    # NEW: Get Sheet URL from Environment Variable (Server Side)
    # We no longer ask the frontend for this.
    sheet_url = os.getenv("DEFAULT_SHEET_URL")
    
    if not user_password or not message_body:
        return jsonify({"error": "Missing password or message"}), 400

    if not sheet_url:
        return jsonify({"error": "Server Error: DEFAULT_SHEET_URL is not set in Environment Variables."}), 500

    # 2. PASSWORD CHECK
    if user_password != ADMIN_PASSWORD:
        return jsonify({"error": "Incorrect Confirmation Password. Aborting."}), 403
    
    # 3. GET CONTACTS
    contacts = get_google_sheet_contacts(sheet_url)
    if contacts is None:
        return jsonify({"error": "Failed to read Google Sheet. Check permissions."}), 500
    
    if len(contacts) == 0:
        return jsonify({"error": "Sheet is empty!"}), 400

    # 4. SEND LOOP
    success_count = 0
    fail_count = 0
    
    print(f"Starting blast to {len(contacts)} numbers...")
    
    for row in contacts:
        # Ensure phone is a string
        phone = str(row.get('Phone', '')).strip()
        
        # Basic cleanup: if user forgot '+', we add it (assuming India '91')
        if not phone.startswith('+'):
            phone = "91" + phone
            
        if phone:
            status, _ = send_whatsapp_template(phone, message_body)
            if status in [200, 201]:
                success_count += 1
            else:
                fail_count += 1
    
    return jsonify({
        "status": "completed",
        "total_attempted": len(contacts),
        "successful": success_count,
        "failed": fail_count
    }), 200

# Webhook for Replies (We will build this out later)
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == os.getenv("VERIFY_TOKEN"):
            return challenge, 200
        return "Forbidden", 403
    return jsonify({"status": "received"}), 200

if __name__ == "__main__":
    app.run(debug=True)