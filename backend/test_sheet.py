import os
import json
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()
# 1. SETUP: The Sheet you want to test
TEST_SHEET_URL = "https://docs.google.com/spreadsheets/d/1G3n5h3uTE0I7Wm9uBZT-XVj2S9X5GwqZ82zG54v-Eug/edit"

def test_google_sheet_connection():
    print("--- 🔍 STARTING FULL SPREADSHEET AUDIT ---")

    # 2. AUTH: Get credentials
    json_creds = os.getenv("GOOGLE_CREDENTIALS")
    if not json_creds:
        print("⚠️ Env variable GOOGLE_CREDENTIALS not found. Checking for 'credentials.json'...")
        if os.path.exists("credentials.json"):
            with open("credentials.json", "r") as f:
                json_creds = f.read()
        else:
            print("❌ ERROR: No credentials found!")
            return

    try:
        # 3. CONNECT
        creds_dict = json.loads(json_creds)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        print("✅ Authorized with Google API.")

        # 4. OPEN SPREADSHEET (The whole file)
        print(f"📂 Opening Spreadsheet...")
        spreadsheet = client.open_by_url(TEST_SHEET_URL)
        
        # Get ALL tabs (worksheets)
        worksheets = spreadsheet.worksheets()
        print(f"📊 Found {len(worksheets)} sheets (tabs) in this file.\n")

        # 5. LOOP THROUGH EVERY TAB
        for sheet in worksheets:
            print(f"🔹 ANALYZING TAB: '{sheet.title}'")
            try:
                data = sheet.get_all_records()
                
                if len(data) == 0:
                    print("   ⚠️ This tab is empty.\n")
                    continue
                
                # Analyze Headers (Keys of the first row)
                headers = list(data[0].keys())
                print(f"   📝 Columns Found: {headers}")
                
                # Check for Phone/Email columns specifically
                phone_cols = [h for h in headers if 'phone' in h.lower() or 'mobile' in h.lower() or 'usdlk' in h.lower()]
                email_cols = [h for h in headers if 'email' in h.lower()]
                
                if phone_cols:
                    print(f"   📞 Phone Data will be pulled from: {phone_cols}")
                else:
                    print("   ❌ WARNING: No obvious Phone column found (looked for phone, mobile, usdlk)")

                if email_cols:
                    print(f"   Cc Email Data will be pulled from: {email_cols}")
                else:
                    print("   ❌ WARNING: No obvious Email column found")

                # Print first 3 rows as sample
                print(f"   👀 First 3 Rows Sample:")
                for i, row in enumerate(data[:3], 1):
                    print(f"      Row {i}: {row}")
                
                print(f"   (Total rows in this tab: {len(data)})\n")
                
            except Exception as e:
                print(f"   ❌ Error reading tab '{sheet.title}': {e}\n")

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    test_google_sheet_connection()