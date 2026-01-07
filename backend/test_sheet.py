import os
import json
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()
# 1. SETUP: The Sheet you want to test
TEST_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_xaRwkaC_OvGPECQSl9CaEbXFYSKbP2kbP4CE9Fdc8A/edit?gid=0#gid=0"

def test_google_sheet_connection():
    print("--- 🔍 STARTING GOOGLE SHEETS TEST ---")

    # 2. AUTH: Get credentials from Environment or File
    json_creds = os.getenv("GOOGLE_CREDENTIALS")
    
    # If env var is empty, try looking for the local file (Local testing fallback)
    if not json_creds:
        print("⚠️  Env variable GOOGLE_CREDENTIALS not found. Checking for 'credentials.json' file...")
        if os.path.exists("credentials.json"):
            with open("credentials.json", "r") as f:
                json_creds = f.read()
        else:
            print("❌ ERROR: No credentials found! Set GOOGLE_CREDENTIALS env var or have credentials.json file.")
            return

    try:
        # 3. CONNECT: Parse JSON and authorize
        creds_dict = json.loads(json_creds)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        print("✅ Authorized successfully with Google API.")

        # 4. FETCH: Open the sheet
        print(f"📂 Attempting to open sheet...")
        sheet = client.open_by_url(TEST_SHEET_URL).sheet1
        
        # 5. READ: Get all data
        data = sheet.get_all_records()
        
        print(f"✅ Connection Successful! Found {len(data)} rows.")
        print("\n--- 📊 DATA CONTENT ---")
        if len(data) == 0:
            print("(The sheet is empty)")
        else:
            for i, row in enumerate(data, 1):
                print(f"Row {i}: {row}")
                
    except gspread.exceptions.APIError as e:
        print(f"\n❌ API ERROR: Google refused the connection.")
        print(f"Reason: {e}")
        print("💡 TIP: Did you share the sheet with the 'client_email' inside your credentials.json?")
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    test_google_sheet_connection()