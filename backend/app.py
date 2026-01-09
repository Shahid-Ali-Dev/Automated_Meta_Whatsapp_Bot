# app.py
import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from services import get_google_sheet_contacts, send_whatsapp_template, get_groq_response, send_whatsapp_text, send_brevo_email, get_sheet_titles

load_dotenv()
app = Flask(__name__)
# Allow Vercel frontend to talk to this backend
CORS(app, resources={r"/*": {"origins": "*"}})

# Security: The password required to fire the blast
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "default_secret") 

# --- STATIC RESPONSE CONFIGURATION ---

# 1. GREETINGS
GREETING_KEYWORDS = [
    "hi", "hello", "hii", "hiii", "helloo", "hey", "hola", "hlo", "heyy", "namaste", "namaskar", 
    "hi?", "hello?", "hey?", "start", "good morning", "good evening"
]

STATIC_GREETING = """Hello! 👋 Welcome to *Shout OTB*.

*About Us:*
We are a Creative Marketing & Branding Company based in Bhopal, India, driven by passion and defined by innovation.

*Our Services:*
📈 *Marketing & Branding* to build your identity
🚀 *Performance Marketing* to boost your sales
🤖 *AI & Automation* to save you time
🛍️ *Retail & E-commerce* to manage your online stores
🎨 *3D Animation & Modeling* to make your product stand out

*Ready to start?*
📞 Call us: *+91 9752000546*
🌐 Visit: https://shoutotb.com
📲 Email: services@shoutotb.com

Let's discuss how we can help you achieve your business goals. What brings you here today?"""

# 2. PRICING & COST
PRICING_KEYWORDS = [
    "price", "pricing", "cost", "costs", "charge", "charges", "rate", "rates", "package", "packages",
    "price?", "pricing?", "cost?", "how much", "how much?"
]

STATIC_PRICING = """💰 *Pricing & Packages*

At *Shout OTB*, we don't believe in "one-size-fits-all." Your business is unique, and your marketing plan should be too.

*Our pricing depends on:*
🔹 The scope of work (e.g., Logo vs. Full Rebranding)
🔹 Duration of the campaign
🔹 Platform selection (Meta, Google, Amazon, etc.)

*Want a Custom Quote?*
Let's have a quick chat to understand your needs.

📞 *Call for Estimate:* +91 9752000546
📧 *Email:* services@shoutotb.com"""

# 3. LOCATION & ADDRESS
LOCATION_KEYWORDS = [
    "location", "address", "where", "where?", "office", "bhopal", "city", "located", "location?", "address?"
]

STATIC_LOCATION = """📍 *Visit Our Office*

We are located in the heart of Bhopal!

*Shout OTB HQ*
🏢 A-17 Pallavi Nagar,
Bawadiya Kalan,
Bhopal - 462026, M.P., India.

*Office Hours:*
Monday - Saturday: 10:00 AM - 7:00 PM

🌐 *Google Maps:* https://maps.app.goo.gl/YourMapLinkHere""" 

# (Note: Replace the map link above if you have a real GMB link)

# 4. SERVICES (Standalone)
SERVICES_KEYWORDS = [
    "service", "services", "work", "what do you do", "offer", "offering", "services?", 
    "view services", "our services", "check services" # <--- Added these
]

STATIC_SERVICES = """🚀 *Our Premium Services*

We provide end-to-end digital solutions to help you scale. Here are the details:

1️⃣ *Marketing & Branding*
• Logo Design & Brand Identity
• Visual Guidelines & Strategy
• Rebranding Campaigns

2️⃣ *Performance Marketing*
• Meta Ads (Facebook/Instagram) with high ROAS
• Google Ads (Search/Display/Youtube)
• Conversion Rate Optimization (CRO)

3️⃣ *AI & Automation*
• Custom WhatsApp Chatbots (Like this one!)
• CRM Integration (HubSpot, Zoho)
• Automated Lead Nurturing Workflows

4️⃣ *Retail & E-commerce*
• Amazon/Flipkart Store Management
• Shopify Website Development
• Inventory & Listing Optimization

5️⃣ *3D Animation & Modeling*
• High-end 3D Product Reveals
• Social Media & Ads (FOOH)
• Architectural Visualization

*Which service would you like to discuss?* 👇"""

# 5. THANKS / CLOSING
THANKS_KEYWORDS = [
    "thanks", "thank you", "thx", "tysm", "bye", "goodbye", "ok thanks", "okay thanks", "cool", "great"
]

STATIC_THANKS = """You're welcome! 🤝

We look forward to working with you. If you have any more questions, just ask!

*Team Shout OTB*
📞 +91 9752000546"""

@app.route("/")
def home():
    return jsonify({"status": "Backend is running", "platform": "Render"}), 200

@app.route("/api/get-sheet-names", methods=["GET"])
def get_sheets():
    sheet_url = os.getenv("DEFAULT_SHEET_URL")
    if not sheet_url:
        return jsonify({"error": "No sheet URL configured"}), 500

    titles = get_sheet_titles(sheet_url)
    return jsonify({"sheets": titles}), 200

@app.route("/api/send-blast", methods=["POST"])
def send_blast():
    data = request.json
    
    # 1. INPUTS
    user_password = data.get("password")
    message_body = data.get("message")
    image_url = data.get("image_url")
    
    # Checkbox States
    send_whatsapp_flag = data.get("send_whatsapp", False)
    send_email_flag = data.get("send_email", False)
    selected_tabs = data.get("selected_tabs", ["ALL"])

    sheet_url = os.getenv("DEFAULT_SHEET_URL")
    
    if not user_password or not message_body:
        return jsonify({"error": "Missing inputs"}), 400
    if user_password != ADMIN_PASSWORD:
        return jsonify({"error": "Wrong Password"}), 403
    
    if not send_whatsapp_flag and not send_email_flag:
        return jsonify({"error": "Please select at least one sending method."}), 400

    # 2. GET CONTACTS (This returns duplicates if they have different emails, which is GOOD)
    contacts = get_google_sheet_contacts(sheet_url, selected_tabs)
    if not contacts:
        return jsonify({"error": "Sheet error or empty"}), 500

    # 3. SEND LOOP
    stats = {"whatsapp_sent": 0, "whatsapp_fail": 0, "email_sent": 0, "email_fail": 0}
    
    # --- NEW: DUPLICATE PROTECTION SETS ---
    sent_phones = set()
    sent_emails = set()
    
    print(f"Starting blast... WA: {send_whatsapp_flag}, Email: {send_email_flag}")
    
    for row in contacts:
        # --- CLEAN NAME ---
        raw_name = str(row.get('Name', 'Valued Customer')).strip()
        clean_name = raw_name.split('-')[0].split('|')[0].strip() or "Valued Customer"

        # --- OPTION 1: WHATSAPP ---
        if send_whatsapp_flag:
            raw_phone = str(row.get('Phone', '')).strip()
            # Clean the phone number
            phone = raw_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if phone.startswith('0'): phone = phone[1:]
            
            # Validate format
            if phone and not phone.startswith('011') and len(phone) >= 10:
                if not phone.startswith('91') and not phone.startswith('+'):
                    phone = "91" + phone

                # --- NEW LOGIC: Check if we already messaged this number ---
                if phone in sent_phones:
                    # We skip sending, BUT we don't mark it as a fail. It's just a duplicate.
                    print(f"⏭️ WA Skip: {phone} (Already sent)")
                else:
                    # It's a new number! Send it.
                    status, _ = send_whatsapp_template(phone, clean_name, message_body, image_url)
                    if status in [200, 201]:
                        stats["whatsapp_sent"] += 1
                        sent_phones.add(phone) # Mark as sent so we don't send again
                    else:
                        stats["whatsapp_fail"] += 1

        # --- OPTION 2: EMAIL ---
        if send_email_flag:
            email = str(row.get('Email ids', '')).strip()
            
            # Handle multiple emails
            if ',' in email: email = email.split(',')[0].strip()
            if ' ' in email: email = email.split(' ')[0].strip()

            if email and '@' in email:
                # --- NEW LOGIC: Check if we already emailed this address ---
                if email in sent_emails:
                    print(f"⏭️ Email Skip: {email} (Already sent)")
                else:
                    # It's a new email! Send it.
                    subject = f"Update for {clean_name}"
                    if send_brevo_email(email, subject, message_body, clean_name):
                        stats["email_sent"] += 1
                        sent_emails.add(email) # Mark as sent
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
    # 1. VERIFICATION
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == os.getenv("VERIFY_TOKEN"):
            return challenge, 200
        return "Forbidden", 403

    # 2. INCOMING MESSAGES
    if request.method == "POST":
        data = request.get_json()
        
        # Don't print the huge JSON every time, it clutters logs.
        # print("Incoming Webhook:", data) 

        try:
            if data.get("entry") and data["entry"][0].get("changes"):
                change = data["entry"][0]["changes"][0]["value"]
                
                # --- CASE A: IT IS A STATUS UPDATE (Sent/Delivered/Read/Failed) ---
                if "statuses" in change:
                    status_data = change["statuses"][0]
                    phone = status_data.get("recipient_id")
                    status = status_data.get("status")
                    
                    if status == "failed":
                        errors = status_data.get("errors", [])
                        for error in errors:
                            code = error.get("code")
                            msg = error.get("message")
                            
                            if code == 131049:
                                print(f"🚫 BLOCKED: Meta Spam Filter triggered for {phone}. (Reason: Ecosystem Engagement)")
                                print("   💡 TIP: Send to known numbers first and reply to them to build trust.")
                            elif code == 131053:
                                print(f"❌ UPLOAD FAIL: Image URL is private/broken for {phone}.")
                            else:
                                print(f"⚠️ FAILED: {phone} - Error {code}: {msg}")
                                
                    # Optional: Print success only for debugging
                    # elif status == "sent":
                    #    print(f"✅ Sent to {phone}")

                # --- CASE B: IT IS A MESSAGE (User replied) ---
                elif "messages" in change:
                    message_data = change["messages"][0]
                    phone_no = message_data["from"]
                    
                    if message_data["type"] == "text":
                        user_text = message_data["text"]["body"]
                        # ... (Rest of your chatbot logic: clean_text, static responses, AI) ...
                        clean_text = user_text.lower().strip()
                        
                        # (Keep your existing if/elif/else logic here for GREETING, PRICING, etc.)
                        if clean_text in GREETING_KEYWORDS:
                             send_whatsapp_text(phone_no, STATIC_GREETING)
                        elif any(word in clean_text for word in PRICING_KEYWORDS):
                             send_whatsapp_text(phone_no, STATIC_PRICING)
                        elif any(word in clean_text for word in LOCATION_KEYWORDS):
                             send_whatsapp_text(phone_no, STATIC_LOCATION)
                        elif any(word in clean_text for word in SERVICES_KEYWORDS):
                             send_whatsapp_text(phone_no, STATIC_SERVICES)
                        elif any(word in clean_text for word in THANKS_KEYWORDS):
                             send_whatsapp_text(phone_no, STATIC_THANKS)
                        else:
                             ai_reply = get_groq_response(user_text)
                             send_whatsapp_text(phone_no, ai_reply)

        except Exception as e:
            print(f"Webhook Error: {e}")

        return jsonify({"status": "received"}), 200

if __name__ == "__main__":
    app.run(debug=True)