"""
One-time script: creates ROSTER, CONFIG, ESCALATIONS sheets with headers
and pre-fills CONFIG with defaults from the spec.
"""
import os
from dotenv import load_dotenv

load_dotenv()

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

ROSTER_HEADERS = [
    "intern_id", "full_name", "telegram_user_id", "telegram_username",
    "cohort", "start_date", "end_date", "active", "email", "notes",
]

CHECKIN_HEADERS = [
    "date", "intern_id", "telegram_user_id", "full_name",
    "checkin_timestamp_utc", "checkin_timestamp_edt",
    "message_text", "message_id", "validated", "late", "week_number",
]

ESCALATION_HEADERS = [
    "date", "intern_id", "trigger", "action_taken", "resolved_date", "notes",
]

CONFIG_DEFAULTS = [
    ["checkin_cutoff_time", "17:00"],
    ["morning_reminder_time", "09:30"],
    ["second_reminder_time", "11:30"],
    ["dm_nudge_time", "13:00"],
    ["precut_reminder_time", "17:45"],
    ["report_day", "4"],
    ["report_time", "18:00"],
    ["risk_amber_threshold", "0.70"],
    ["risk_red_threshold", "0.50"],
    ["streak_concern_days", "3"],
    ["retention_weeks", "12"],
    ["admin_telegram_id", ""],
    ["admin_email", "minhluan081294@gmail.com"],
    ["group_chat_id", ""],
]


def main():
    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"], scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"])

    existing = {ws.title for ws in ss.worksheets()}

    for title, headers in [("ROSTER", ROSTER_HEADERS), ("ESCALATIONS", ESCALATION_HEADERS)]:
        if title not in existing:
            ws = ss.add_worksheet(title=title, rows=1000, cols=len(headers))
            ws.append_row(headers)
            print(f"Created sheet: {title}")
        else:
            print(f"Sheet already exists, skipping: {title}")

    if "CONFIG" not in existing:
        ws = ss.add_worksheet(title="CONFIG", rows=50, cols=2)
        ws.append_row(["key", "value"])
        ws.append_rows(CONFIG_DEFAULTS)
        print("Created sheet: CONFIG")
    else:
        print("Sheet already exists, skipping: CONFIG")

    print("Done.")


if __name__ == "__main__":
    main()
