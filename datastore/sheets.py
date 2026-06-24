import os
from datetime import date
from typing import Optional
import gspread
from google.oauth2.service_account import Credentials
from datastore.models import Intern, CheckIn, Config, Escalation

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

_client: Optional[gspread.Client] = None
_spreadsheet: Optional[gspread.Spreadsheet] = None


def _get_spreadsheet() -> gspread.Spreadsheet:
    global _client, _spreadsheet
    if _spreadsheet is None:
        creds = Credentials.from_service_account_file(
            os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"], scopes=SCOPES
        )
        _client = gspread.authorize(creds)
        _spreadsheet = _client.open_by_key(os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"])
    return _spreadsheet


def checkin_sheet_name(iso_week: int, year: int) -> str:
    return f"CHECKINS_{year}_{iso_week:02d}"


def get_all_interns() -> list[Intern]:
    raise NotImplementedError


def get_intern_by_telegram_id(telegram_user_id: int) -> Optional[Intern]:
    raise NotImplementedError


def write_checkin(checkin: CheckIn) -> None:
    raise NotImplementedError


def checkin_exists(message_id: int, week_sheet_name: str) -> bool:
    raise NotImplementedError


def get_checkins_for_week(iso_week: int, year: int) -> list[CheckIn]:
    raise NotImplementedError


def get_config() -> Config:
    raise NotImplementedError


def update_config_key(key: str, value: str) -> None:
    raise NotImplementedError


def write_escalation(escalation: Escalation) -> None:
    raise NotImplementedError


def get_checkins_for_date(target_date: date) -> list[CheckIn]:
    raise NotImplementedError


def deactivate_intern(intern_id: str) -> None:
    raise NotImplementedError
