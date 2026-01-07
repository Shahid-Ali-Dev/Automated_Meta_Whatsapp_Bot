import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

load_dotenv()
# Scope for sending emails
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_token():
    print("--- 🔐 GENERATING GMAIL TOKEN ---")
    
    # 1. Get the JSON string from Environment Variable
    # You must set 'GMAIL_CREDENTIALS_JSON' in your .env or system vars
    # It should contain the content of the credentials_gmail.json file you downloaded
    client_config_str = os.getenv("GMAIL_CREDENTIALS_JSON")
    
    if not client_config_str:
        print("❌ ERROR: Env var 'GMAIL_CREDENTIALS_JSON' is missing!")
        print("💡 Paste the content of your downloaded json file into this variable.")
        # Local fallback for testing (Optional)
        if os.path.exists('credentials_gmail.json'):
            print("⚠️ Found local file, using that instead...")
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials_gmail.json', SCOPES)
        else:
            return
    else:
        # Parse the string into a dictionary
        client_config = json.loads(client_config_str)
        
        # Create the flow from the dictionary directly
        flow = InstalledAppFlow.from_client_config(
            client_config, SCOPES)

    # 2. Launch the Browser Login
    print("🚀 Opening browser... Please log in with 'services@shoutotb.com'")
    # We use port 0 to let the OS pick a free open port
    creds = flow.run_local_server(port=0)

    # 3. Print the Token content (So you can copy it to Render env vars)
    print("\n✅ SUCCESS! Authentication complete.")
    
    json_token = creds.to_json()
    
    # Save to file locally (just so you have it)
    with open('token_gmail.json', 'w') as token_file:
        token_file.write(json_token)
        
    print(f"\n--- 📋 COPY THIS CONTENT BELOW FOR 'GMAIL_TOKEN_JSON' ---")
    print(json_token)
    print("---------------------------------------------------------")

if __name__ == '__main__':
    # Local Test: Load .env if you are running locally with python-dotenv
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
        
    get_token()