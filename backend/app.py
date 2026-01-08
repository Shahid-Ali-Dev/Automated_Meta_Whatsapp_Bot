# app.py
import os
import json
import requests
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

import datetime # Add this import at the top

def send_brevo_email(to_email, subject, body_text, user_name="Valued Customer"):
    """
    Sends a Professional HTML email via Brevo using the Shout OTB branded template.
    """
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("SENDER_EMAIL", "services@shoutotb.com")
    
    if not api_key:
        print("❌ Error: BREVO_API_KEY not found.")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    # 1. Format the body text (Convert newlines to HTML breaks)
    formatted_body = body_text.replace("\n", "<br>")
    
    # 2. Get current year for copyright
    current_year = datetime.datetime.now().year

    # 3. THE PROFESSIONAL TEMPLATE
    # We inject {user_name}, {formatted_body}, and {current_year} into the HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Shout OTB Notification</title>
        <style>
            /* --- RESET & BASE --- */
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f5f5f5;
                color: #333;
                line-height: 1.5;
                margin: 0;
                padding: 0;
            }}
            .email-container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08);
            }}
            /* --- HEADER --- */
            .email-header {{
                background: linear-gradient(135deg, #090909 0%, #1e1e1e 100%);
                padding: 30px 20px;
                text-align: center;
                color: white;
            }}
            .branding-container {{ margin-bottom: 10px; }}
            .logo-img {{
                vertical-align: middle;
                width: 50px;
                height: auto;
                margin-right: 10px;
                border-radius: 8px;
            }}
            .logo-text {{
                font-size: 26px;
                color: #f33c52;
                font-weight: 800;
                letter-spacing: -0.5px;
                vertical-align: middle;
                display: inline-block;
            }}
            .email-title {{
                font-size: 20px;
                color: #fff;
                margin-top: 5px;
                font-weight: 600;
                opacity: 0.9;
            }}
            /* --- CONTENT --- */
            .email-content {{
                padding: 30px 20px;
                background-color: #f9f9f9;
                color: #333;
            }}
            .greeting {{
                font-size: 16px;
                color: #f33c52;
                margin-bottom: 15px;
                font-weight: 600;
            }}
            .message-content {{
                font-size: 15px;
                line-height: 1.6;
                margin-bottom: 20px;
            }}
            /* --- FOOTER --- */
            .email-footer {{
                background-color: #f9f9f9;
                padding: 30px 20px;
                text-align: center;
            }}
            .footer-grid {{
                text-align: center;
                padding: 10px 0;
            }}
            .footer-pill {{
                display: inline-block;
                vertical-align: top;
                width: 140px;
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
                padding: 15px 10px;
                margin: 5px;
                text-align: center;
                text-decoration: none;
                transition: all 0.3s ease;
                box-shadow: 0 2px 5px rgba(0,0,0,0.03);
            }}
            .footer-pill:hover {{
                transform: translateY(-2px);
                border-color: #f33c52;
                box-shadow: 0 5px 15px rgba(243, 60, 82, 0.15);
            }}
            .pill-icon {{
                font-size: 22px;
                display: block;
                margin-bottom: 8px;
            }}
            .pill-title {{
                color: #f33c52;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 1px;
                font-weight: 700;
                display: block;
                margin-bottom: 4px;
            }}
            .pill-link {{
                color: #333;
                font-size: 13px;
                text-decoration: none;
                display: block;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                font-weight: 500;
            }}
            .no-reply-note {{
                font-size: 12px;
                color: #555;
                margin-top: 25px;
                margin-bottom: 5px;
                font-style: italic;
                letter-spacing: 0.3px;
            }}
            .copyright {{
                font-size: 12px;
                color: #888;
                margin-top: 25px;
                padding-top: 20px;
                border-top: 1px solid #e0e0e0;
            }}
            /* Mobile Responsiveness */
            @media (max-width: 480px) {{
                .footer-pill {{
                    width: 100%;
                    display: block;
                    margin: 10px 0;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <div class="branding-container">
                    <img src="https://res.cloudinary.com/dru5oqalj/image/upload/w_80,h_80,c_pad,b_transparent,f_auto,q_auto/v1764500530/Asset_22_dbva0l.png" 
                         alt="Logo" class="logo-img" width="50" height="50">
                    <span class="logo-text">SHOUT OTB</span>
                </div>
                <h2 class="email-title">{subject}</h2>
            </div>
            
            <div class="email-content">
                <div class="greeting">Hello {user_name},</div>
                <div class="message-content">
                    {formatted_body}
                </div>
            </div>
            
            <div class="email-footer">
                <div class="footer-grid">
                    <a href="mailto:services@shoutotb.com" class="footer-pill">
                        <span class="pill-icon">✉️</span>
                        <span class="pill-title">Email</span>
                        <span class="pill-link">services@shoutotb.com</span>
                    </a>
                    <a href="tel:+919752000546" class="footer-pill">
                        <span class="pill-icon">📞</span>
                        <span class="pill-title">Phone</span>
                        <span class="pill-link">+91 97520 00546</span>
                    </a>
                    <a href="https://shoutotb.com" class="footer-pill">
                        <span class="pill-icon">🌐</span>
                        <span class="pill-title">Website</span>
                        <span class="pill-link">shoutotb.com</span>
                    </a>
                </div>
                
                <div class="no-reply-note">
                    This is an automated notification. Please do not reply directly to this email.
                </div>
                
                <div class="copyright">
                    © {current_year} Shout OTB. All rights reserved.
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    payload = {
        "sender": {"name": "Shout OTB Team", "email": sender_email},
        "to": [{"email": to_email, "name": user_name}],
        "subject": subject,
        "htmlContent": html_content
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            return True
        else:
            print(f"📧 Brevo Error: {response.text}")
            return False
    except Exception as e:
        print(f"📧 Connection Error: {e}")
        return False
    
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