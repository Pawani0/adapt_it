import json
import os
from datetime import datetime
import config

# Try importing gspread and google auth
GSPREAD_AVAILABLE = False
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    pass

CREDENTIALS_FILE = 'credentials.json'


def _has_google_credentials():
    return bool(os.environ.get("GOOGLE_CREDENTIALS_JSON")) or os.path.exists(CREDENTIALS_FILE)


def _load_google_credentials(scopes):
    credentials_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if credentials_json:
        return Credentials.from_service_account_info(json.loads(credentials_json), scopes=scopes)
    return Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)

def get_headers():
    question_count = getattr(config, "QUIZ_QUESTION_COUNT", 5)
    return ["Name", "Email", "Score", "Time Taken", "Tab Switches", "Date"] + [
        f"Q{i}" for i in range(1, question_count + 1)
    ]

def log_submission(name, email, score, time_taken, tab_switches, answers):
    """
    Appends a new submission row to the configured Google Sheet.
    Columns: Name, Email, Score, Time Taken, Tab Switches, Date, Q1...
    
    If Google credentials are missing or gspread is not available,
    it falls back to writing to a local text log for simulation.
    """
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    time_taken_str = f"{time_taken}s"
    
    # Check if we should simulate
    simulate = False
    reason = ""
    
    if not GSPREAD_AVAILABLE:
        simulate = True
        reason = "gspread or google-auth libraries not installed"
    elif not _has_google_credentials():
        simulate = True
        reason = "Google service account credentials are not configured"
    elif config.GOOGLE_SHEET_ID == "your-google-sheet-id-here" or not config.GOOGLE_SHEET_ID:
        simulate = True
        reason = "GOOGLE_SHEET_ID is not configured in config.py"

    headers = get_headers()
    question_count = len(headers) - 6
    normalized_answers = list(answers[:question_count])
    while len(normalized_answers) < question_count:
        normalized_answers.append("")

    row_data = [name, email, score, time_taken_str, tab_switches, date_str] + normalized_answers
    
    if simulate:
        print(f"[*] Simulation Mode (Sheets API): {reason}")
        print(f"[+] Appending mock row to local sheets simulation log:")
        print(f"    {row_data}")
        
        # Log to a local simulation file
        log_file = "mock_sheets_log.txt"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("\t|\t".join(map(str, row_data)) + "\n")
        except Exception as e:
            print(f"[-] Failed to write to mock log: {e}")
        return True

    # Real sheets logger
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = _load_google_credentials(scopes)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key(config.GOOGLE_SHEET_ID).get_worksheet(0)
        
        # Ensure the first row is always the expected header row.
        existing_values = sheet.get_all_values()
        if not existing_values:
            sheet.append_row(headers)
        elif existing_values[0] != headers:
            sheet.insert_row(headers, 1)
            
        sheet.append_row(row_data)
        print(f"[+] Real-time result appended to Google Sheet for {name}.")
        return True
    except Exception as e:
        print(f"[-] Failed to append row to real Google Sheet: {e}")
        print("[*] Falling back to local log simulation...")
        # Write to mock log as secondary fallback
        with open("mock_sheets_log.txt", "a", encoding="utf-8") as f:
            f.write("\t|\t".join(map(str, row_data)) + " (Fallback due to error)\n")
        return False

if __name__ == "__main__":
    # Test sheets logger (will simulate by default)
    log_submission("Alex Mercer", "alex@example.com", 4, 120, 0, ["A", "B", "C", "D", "A"])
