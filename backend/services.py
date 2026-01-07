import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from groq import Groq
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

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

def send_gmail(to_email, subject, body_text, user_name="Valued Customer"):
    """
    Sends a Professional HTML email via Gmail API.
    """
    try:
        # 1. LOAD CREDENTIALS
        token_json = os.getenv("GMAIL_TOKEN_JSON")
        if not token_json:
            print("❌ Error: GMAIL_TOKEN_JSON not found in env.")
            return False

        creds = Credentials.from_authorized_user_info(json.loads(token_json))
        service = build('gmail', 'v1', credentials=creds)

        # 2. PREPARE CONTENT
        # Convert newlines in the message to HTML line breaks so it looks right
        formatted_body = body_text.replace("\n", "<br>")

        # 3. HTML TEMPLATE (The Professional Design)
        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333;">
            
            <h2 style="color: #2c3e50;">Hello {user_name},</h2>
            
            <div style="font-size: 16px; margin-bottom: 30px;">
                {formatted_body}
            </div>

            <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 30px 0;">
            
            <div style="color: #7f8c8d; font-size: 13px;">
                <strong>Team Shout OTB</strong><br>
                <em>"Driven by Passion. Defined by Innovation."</em><br>
                <br>
                📍 A-17 Pallavi Nagar, Bhopal, India<br>
                📞 +91 97520 00546<br>
                🌐 <a href="https://shoutotb.com" style="color: #FF6B35; text-decoration: none;">www.shoutotb.com</a>
            </div>

          </body>
        </html>
        """

        # 4. CREATE MESSAGE
        # We use 'html' instead of 'plain'
        message = MIMEText(html_content, 'html') 
        message['to'] = to_email
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': raw_message}

        # 5. SEND
        service.users().messages().send(userId="me", body=create_message).execute()
        return True

    except Exception as e:
        print(f"📧 Email Error: {e}")
        return False
        
# --- THE MASTER PROMPT ---
# This variable holds all the knowledge the bot needs about Shout OTB.
SYSTEM_PROMPT = """
You are the AI Business Assistant for 'Shout OTB' (Shout Out Of The Box), a creative marketing agency based in Bhopal, India.
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

1. **HEADERS**: Use asterisks for headers. Example: *Our Services:*
2. **SPACING**: key rule -> NEVER write big blocks of text. Use double line breaks between sections.
3. **LISTS**: Use emojis as bullet points for lists.
4. **EMPHASIS**: Use *bold* for key terms (like the phone number).
5. **STRUCTURE**:
   - Start with a short, warm greeting.
   - Answer the question clearly using bullet points or short paragraphs.
   - End with a distinct Call to Action.

--- EXAMPLE OF IDEAL OUTPUT ---
"Hello! 👋 Welcome to Shout OTB.

*Here is how we can help you:*
🚀 *Performance Marketing* to boost your sales.
🎨 *3D Animation* to make your product stand out.
🤖 *AI Automation* to save you time.

Our pricing is transparent and depends on your specific needs.

*Ready to start?*
📞 Call us: *+91 9752000546*
🌐 Visit: shoutotb.com"

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