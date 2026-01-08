# services.py
import os
import datetime
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
    Connects to Google Sheets and returns a consolidated list of contacts 
    from ALL tabs, handling mixed column names (Phone, Mobile, Contact, etc.).
    """
    try:
        # 1. AUTHENTICATION
        json_creds = os.getenv("GOOGLE_CREDENTIALS")
        if not json_creds:
            if os.path.exists("credentials.json"):
                with open("credentials.json", "r") as f:
                    json_creds = f.read()
            else:
                print("❌ No credentials found!")
                return None

        creds_dict = json.loads(json_creds)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 2. OPEN FILE
        spreadsheet = client.open_by_url(sheet_url)
        all_contacts = []
        seen_contacts = set()
        
        worksheets = spreadsheet.worksheets()
        print(f"📊 Found {len(worksheets)} sheets. combining data...")

        # 3. LOOP TABS
        for sheet in worksheets:
            try:
                # Get raw records
                records = sheet.get_all_records()
                
                if not records:
                    continue

                # 4. SMART COLUMN MAPPING
                # We need to find which key corresponds to Phone, Email, Name in THIS specific tab
                headers = list(records[0].keys())
                
                # Define possible aliases (lowercase for easier matching)
                phone_aliases = ['phone', 'mobile', 'usdlk', 'contact', 'contact number', 'corporate phone']
                email_aliases = ['email', 'email ids', 'email id', 'email address']
                name_aliases = ['name', 'company name', 'company', 'brand', 'first name']

                # Find the actual column name used in this sheet
                phone_key = next((h for h in headers if h.lower() in phone_aliases), None)
                email_key = next((h for h in headers if h.lower() in email_aliases), None)
                name_key = next((h for h in headers if h.lower() in name_aliases), None)

                for row in records:
                    # Extract using the found keys
                    phone = str(row.get(phone_key, '')).strip() if phone_key else ""
                    email = str(row.get(email_key, '')).strip() if email_key else ""
                    name = str(row.get(name_key, '')).strip() if name_key else "Valued Customer"

                    # Special Case: If name is split (First Name / Last Name), combine them
                    if name_key and name_key.lower() == 'first name':
                        last_name = str(row.get('Last Name', '')).strip()
                        if last_name:
                            name = f"{name} {last_name}"

                    # Create a standardized row object
                    clean_row = {
                        'Phone': phone,
                        'Email ids': email,
                        'Name': name,
                        'Source_Tab': sheet.title 
                    }

                    # --- UPDATED DEDUPLICATION LOGIC ---
                    # Old way: unique_key = phone if phone else email
                    # This caused the issue because if phone matched, it ignored different emails.
                    
                    # New Way: Combine Phone AND Email to make the key.
                    # This means (Phone1, EmailA) is different from (Phone1, EmailB).
                    unique_key = f"{phone}_{email}"

                    if unique_key not in seen_contacts:
                        seen_contacts.add(unique_key)
                        all_contacts.append(clean_row)
                        
            except Exception as e:
                print(f"⚠️ Skipped tab '{sheet.title}': {e}")
                continue

        print(f"✅ Extracted {len(all_contacts)} unique contacts.")
        return all_contacts

    except Exception as e:
        print(f"Google Sheet Error: {e}")
        return None

def send_whatsapp_template(to_number, user_name, custom_message, image_url=None):
    """
    Sends a WhatsApp template with 2 variables: {{1}}=Name, {{2}}=Message.
    - If image_url exists -> uses 'promo_with_image' (Header Image + Body).
    - If no image -> uses 'promo_text_v2' (Text Body + Buttons).
    """
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 1. DEFINE THE VARIABLES (Same for both templates)
    # Parameter 1: Name
    # Parameter 2: The Custom Message from your website
    body_parameters = [
        {"type": "text", "text": user_name},
        {"type": "text", "text": custom_message}
    ]

    # 2. CHOOSE TEMPLATE BASED ON IMAGE
    if image_url:
        template_name = "promo_with_image" # Ensure this template in Meta has {{1}} and {{2}}
        components = [
            {
                "type": "header",
                "parameters": [
                    {"type": "image", "image": {"link": image_url}}
                ]
            },
            {
                "type": "body",
                "parameters": body_parameters
            }
        ]
    else:
        template_name = "promo_text_v2" # The new text template with buttons
        components = [
            {
                "type": "body",
                "parameters": body_parameters
            }
        ]

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": components
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.status_code, response.json()
    except Exception as e:
        return 500, str(e)

def send_brevo_email(to_email, subject, body_text, user_name="Valued Customer"):
    """
    Sends a Professional HTML email via Brevo.
    - Inbox Subject: "Update for {Name}"
    - Template Header: "Greetings {Name}! 👋"
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

    formatted_body = body_text.replace("\n", "<br>")
    current_year = datetime.datetime.now().year

    # --- HTML TEMPLATE START ---
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
                
                <h2 class="email-title">Greetings {user_name}! 👋</h2>
                
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
    # --- HTML TEMPLATE END ---

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

# --- THE MASTER PROMPT ---
# This variable holds all the knowledge the bot needs about Shout OTB.
SYSTEM_PROMPT = """
You are the AI Business Assistant for 'Shout OTB' (Shout Out Of The Box), a Creative Marketing & Branding agency based in Bhopal, India.
Your goal is to answer client queries professionally, showcase our services, and encourage them to book a consultation or call +91 9752000546.

--- COMPANY PROFILE ---
Name: Shout OTB
Founder: Swati Bindha (Founded 2025)
Tagline: "Driven by Passion. Defined by Innovation."
Location: A-17 Pallavi Nagar, Bawadiya Kalan, Bhopal - 462026, M.P., India.
Website: https://shoutotb.com
Contact: +91 9752000546 | services@shoutotb.com
Mission: To democratize access to premium digital solutions.

--- OUR SERVICES ---
1. Marketing & Branding (Logo, Identity, Strategy)
2. Performance Marketing (Meta Ads, Google Ads, ROAS focus)
3. AI & Automation (Chatbots, Workflow Automation)
4. Retail & E-commerce (Amazon/Flipkart/Shopify Management)
5. 3D Animation & Modeling (CGI Ads, Visuals)

--- WHATSAPP FORMATTING RULES (STRICT) ---
You are chatting on WhatsApp. You MUST format your text to look clean and structured:

1. **NO REPETITIVE INTROS**: Do NOT say "Welcome to Shout OTB" or introduce the company again. The user already knows who we are. Jump STRAIGHT into the answer.
2. **HEADERS**: Use asterisks for headers. Example: *Our Services:*
3. **SPACING**: Use double line breaks between sections.
4. **LISTS**: Use emojis as bullet points for lists.
5. **EMPHASIS**: Use *bold* for key terms (like the phone number).
6. **STRUCTURE**:
   - Answer the specific question directly and concisely.
   - Use bullet points if listing items.
   - End with a Call to Action (Book a call/Visit site).

--- EXAMPLE OF IDEAL OUTPUT (If user asks "Do you do 3D?") ---
"Yes, we specialize in high-end *3D Animation & Modeling*! 🎨

We can help you with:
✨ Product Visualization
🎥 CGI Ads for Social Media
architectural Walkthroughs

*Want to see our portfolio?*
🌐 Visit: shoutotb.com
📞 Call us: *+91 9752000546*"

--- END OF RULES ---
Now, reply to the user based on these rules.
"""

def get_groq_response(user_text):
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT  # <--- WE INJECT THE KNOWLEDGE HERE
                },
                {
                    "role": "user",
                    "content": user_text,
                }
            ],
            model="llama-3.3-70b-versatile",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Groq Error: {e}")
        return "I'm having trouble connecting right now. Please call us directly at +91 9752000546."

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