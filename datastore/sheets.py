import json
import os
import difflib
import subprocess
import time
from datetime import date, datetime
from typing import Optional
import anthropic
import gspread
from google.auth.exceptions import TransportError
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError
from requests.exceptions import ConnectionError, Timeout
from datastore.models import Intern, CheckIn, Config, Escalation

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

_client: Optional[gspread.Client] = None
_spreadsheet: Optional[gspread.Spreadsheet] = None
_CACHE_TTL_SECONDS = 300
_interns_cache: tuple[float, list[Intern]] | None = None
_config_cache: tuple[float, Config] | None = None


def _is_retryable_sheets_error(exc: Exception) -> bool:
    if isinstance(exc, (ConnectionError, Timeout, TransportError)):
        return True
    if isinstance(exc, APIError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return status == 429 or (status is not None and 500 <= status < 600)
    return False


def _with_sheets_retry(fn, *, attempts: int = 4):
    delay = 1.0
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == attempts or not _is_retryable_sheets_error(exc):
                raise
            time.sleep(delay)
            delay *= 2


def _get_spreadsheet() -> gspread.Spreadsheet:
    global _client, _spreadsheet
    if _spreadsheet is None:
        creds = Credentials.from_service_account_file(
            os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"], scopes=SCOPES
        )
        _client = gspread.authorize(creds)
        _spreadsheet = _client.open_by_key(os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"])
    return _spreadsheet


def _cache_fresh(ts: float) -> bool:
    return time.monotonic() - ts < _CACHE_TTL_SECONDS


def _invalidate_roster_cache() -> None:
    global _interns_cache
    _interns_cache = None


def _invalidate_config_cache() -> None:
    global _config_cache
    _config_cache = None


_SCHEDULE_PARSE_PROMPT = (
    'Parse this intern work schedule into JSON. Output ONLY a JSON array — no explanation.\n'
    'Each element: {{"days": [...], "start": "HH:MM", "end": "HH:MM"}}\n'
    'days: full names "Mon","Tue","Wed","Thu","Fri","Sat","Sun"\n'
    'start/end: 24-hour HH:MM in America/New_York.\n'
    'Timezone conversions: CST/CDT add 1h, PDT add 3h, PST add 4h, EDT/EST/ET no change.\n'
    'Day shorthands: M=Mon T=Tue W=Wed Th=Thu F=Fri Sa=Sat Su=Sun SS=Sat+Sun FSS=Fri+Sat+Sun.\n'
    'No days specified → assume Mon-Fri. Blank/unparseable → return [].\n'
    'Obvious typo where end < start and context implies PM → convert end to PM.\n\n'
    'Schedule text: "{raw}"'
)


CLAUDE_BIN = "/usr/local/bin/claude"


def _strip_code_fence(out: str) -> str:
    if out.startswith("```"):
        lines = out.split("\n")
        out = "\n".join(lines[1:])
        if out.endswith("```"):
            out = out[: out.rfind("```")]
    return out.strip()


def _parse_schedule_via_claude(raw: str) -> str:
    """Parse freeform schedule text into a schedule_json string.

    Prefers the local Claude Code CLI when present (uses your existing
    subscription, no per-call API billing) -- the normal case on a dev
    machine. Falls back to the Claude API via ANTHROPIC_API_KEY when the CLI
    isn't installed (e.g. a server). Returns "[]" if neither is available or
    the call fails for any reason -- self-registration should never break
    because schedule parsing is unavailable."""
    if not raw or not raw.strip():
        return "[]"
    prompt = _SCHEDULE_PARSE_PROMPT.format(raw=raw.replace('"', "'"))
    try:
        if os.path.exists(CLAUDE_BIN):
            result = subprocess.run(
                [CLAUDE_BIN, "--print", "--output-format", "text"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=90,
            )
            if result.returncode != 0:
                return "[]"
            out = _strip_code_fence(result.stdout.strip())
        else:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if not api_key:
                return "[]"
            client = anthropic.Anthropic(api_key=api_key)
            model = os.environ.get("CLAUDE_SUMMARY_MODEL", "claude-haiku-4-5-20251001")
            response = client.messages.create(
                model=model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            out = _strip_code_fence(response.content[0].text.strip())
        json.loads(out)  # validate — raises if bad
        return out
    except Exception:
        return "[]"


def checkin_sheet_name(iso_week: int, year: int) -> str:
    return f"CHECKINS_{year}_{iso_week:02d}"


def get_source_team_members() -> list[dict]:
    """Read directly from 'Team Members' tab — the source of truth roster."""
    ss = _get_spreadsheet()
    ws = _with_sheets_retry(lambda: ss.worksheet("Team Members"))
    return _with_sheets_retry(ws.get_all_records)


def _get_or_create_checkin_sheet(sheet_name: str) -> gspread.Worksheet:
    ss = _get_spreadsheet()
    try:
        return _with_sheets_retry(lambda: ss.worksheet(sheet_name))
    except gspread.WorksheetNotFound:
        headers = [
            "date", "intern_id", "telegram_user_id", "full_name",
            "checkin_timestamp_utc", "checkin_timestamp_edt",
            "message_text", "message_id", "validated", "late", "week_number",
        ]
        ws = _with_sheets_retry(lambda: ss.add_worksheet(title=sheet_name, rows=5000, cols=len(headers)))
        _with_sheets_retry(lambda: ws.append_row(headers))
        return ws


def _get_or_create_unmatched_checkins_sheet() -> gspread.Worksheet:
    ss = _get_spreadsheet()
    try:
        return _with_sheets_retry(lambda: ss.worksheet("UNMATCHED_CHECKINS"))
    except gspread.WorksheetNotFound:
        headers = [
            "date", "reason", "telegram_user_id", "telegram_username",
            "telegram_name", "chat_id", "message_id", "timestamp_utc",
            "timestamp_edt", "message_text",
        ]
        ws = _with_sheets_retry(lambda: ss.add_worksheet(title="UNMATCHED_CHECKINS", rows=1000, cols=len(headers)))
        _with_sheets_retry(lambda: ws.append_row(headers))
        return ws


def unmatched_checkin_exists(telegram_user_id: int, message_id: int) -> bool:
    try:
        ws = _get_or_create_unmatched_checkins_sheet()
        records = _with_sheets_retry(ws.get_all_records)
        return any(
            int(r.get("telegram_user_id", 0)) == telegram_user_id
            and int(r.get("message_id", 0)) == message_id
            for r in records
        )
    except gspread.WorksheetNotFound:
        return False


def write_unmatched_checkin(
    *,
    reason: str,
    telegram_user_id: int,
    telegram_username: str | None,
    telegram_name: str,
    chat_id: int,
    message_id: int,
    timestamp_utc: datetime,
    timestamp_edt: datetime,
    message_text: str,
) -> None:
    if unmatched_checkin_exists(telegram_user_id, message_id):
        return
    ws = _get_or_create_unmatched_checkins_sheet()
    _with_sheets_retry(lambda: ws.append_row([
        timestamp_edt.date().isoformat(),
        reason,
        telegram_user_id,
        telegram_username or "",
        telegram_name,
        chat_id,
        message_id,
        timestamp_utc.isoformat(),
        timestamp_edt.isoformat(),
        message_text[:200],
    ]))


def get_all_interns() -> list[Intern]:
    global _interns_cache
    if _interns_cache and _cache_fresh(_interns_cache[0]):
        return list(_interns_cache[1])

    ss = _get_spreadsheet()
    ws = _with_sheets_retry(lambda: ss.worksheet("ROSTER"))
    records = _with_sheets_retry(ws.get_all_records)
    interns = []
    for r in records:
        if not r.get("intern_id"):
            continue
        try:
            interns.append(Intern(
                intern_id=str(r["intern_id"]),
                full_name=str(r["full_name"]),
                telegram_user_id=int(r["telegram_user_id"]) if r.get("telegram_user_id") else 0,
                telegram_username=str(r["telegram_username"]) if r.get("telegram_username") else None,
                cohort=str(r.get("cohort", "")),
                start_date=date.fromisoformat(str(r["start_date"])) if r.get("start_date") else date(2026, 1, 1),
                end_date=date.fromisoformat(str(r["end_date"])) if r.get("end_date") else date(2099, 12, 31),
                active=str(r.get("active", "TRUE")).upper() == "TRUE",
                email=str(r["email"]) if r.get("email") else None,
                notes=str(r["notes"]) if r.get("notes") else None,
                schedule_json=str(r["schedule_json"]) if r.get("schedule_json") else None,
                schedule_raw=str(r["schedule_raw"]) if r.get("schedule_raw") else None,
            ))
        except Exception:
            continue
    _interns_cache = (time.monotonic(), interns)
    return list(interns)


def get_intern_by_telegram_id(telegram_user_id: int) -> Optional[Intern]:
    for intern in get_all_interns():
        if intern.telegram_user_id == telegram_user_id and intern.active:
            return intern
    return None


def _extract_name(record: dict) -> str:
    """Pull a full name string from a sheet record, tolerating varied column names."""
    return (
        record.get("full_name") or record.get("Full Name") or
        record.get("name") or record.get("Name") or
        (f"{record.get('first_name', '')} {record.get('last_name', '')}".strip()) or
        (f"{record.get('First Name', '')} {record.get('Last Name', '')}".strip()) or ""
    )


def find_intern_candidate_by_name(query: str) -> tuple[Optional[dict], float]:
    """Fuzzy-match query against Team Members sheet. Returns (record, score) or (None, 0)."""
    members = get_source_team_members()
    query_lower = query.lower().strip()
    best_record = None
    best_score = 0.0
    for member in members:
        full_name = _extract_name(member)
        if not full_name:
            continue
        score = difflib.SequenceMatcher(None, query_lower, full_name.lower().strip()).ratio()
        if score > best_score:
            best_score = score
            best_record = member
    return best_record, best_score


def is_already_registered(telegram_user_id: int) -> bool:
    return any(i.telegram_user_id == telegram_user_id for i in get_all_interns())


def register_intern_from_dm(telegram_user_id: int, telegram_username: Optional[str], member: dict) -> None:
    """Append a self-registered intern to the ROSTER sheet."""
    ss = _get_spreadsheet()
    ws = _with_sheets_retry(lambda: ss.worksheet("ROSTER"))
    full_name = _extract_name(member)
    intern_id = str(
        member.get("intern_id") or member.get("Intern ID") or member.get("id") or
        full_name.lower().replace(" ", "_")
    )
    cohort = str(member.get("cohort") or member.get("Cohort") or "")
    start_date = str(member.get("start_date") or member.get("Start Date") or "")
    end_date = str(member.get("end_date") or member.get("End Date") or "")
    email = str(member.get("email") or member.get("Email") or "")
    raw_schedule = str(
        member.get("Preferred Shift | Interns Hours") or
        member.get("preferred_shift") or ""
    ).strip()
    schedule_json = _parse_schedule_via_claude(raw_schedule)
    _with_sheets_retry(lambda: ws.append_row([
        intern_id, full_name, telegram_user_id,
        telegram_username or "", cohort, start_date, end_date,
        "TRUE", email, "self-registered via DM", schedule_json, raw_schedule,
    ]))
    _invalidate_roster_cache()


def write_checkin(checkin: CheckIn) -> None:
    year = checkin.checkin_timestamp_utc.year
    sheet_name = checkin_sheet_name(checkin.week_number, year)
    ws = _get_or_create_checkin_sheet(sheet_name)
    _with_sheets_retry(lambda: ws.append_row([
        checkin.date.isoformat(),
        checkin.intern_id,
        checkin.telegram_user_id,
        checkin.full_name,
        checkin.checkin_timestamp_utc.isoformat(),
        checkin.checkin_timestamp_edt.isoformat(),
        checkin.message_text[:200],
        checkin.message_id,
        str(checkin.validated),
        str(checkin.late),
        checkin.week_number,
    ]))


def checkin_exists(message_id: int, week_sheet_name: str) -> bool:
    ss = _get_spreadsheet()
    try:
        ws = _with_sheets_retry(lambda: ss.worksheet(week_sheet_name))
        records = _with_sheets_retry(ws.get_all_records)
        return any(int(r.get("message_id", 0)) == message_id for r in records)
    except gspread.WorksheetNotFound:
        return False


def intern_checked_in_today(intern_id: str, work_date, week_sheet_name: str) -> bool:
    """Return True if this intern already has a check-in row for work_date today."""
    ss = _get_spreadsheet()
    try:
        ws = _with_sheets_retry(lambda: ss.worksheet(week_sheet_name))
        records = _with_sheets_retry(ws.get_all_records)
        date_str = work_date.isoformat()
        return any(
            str(r.get("intern_id", "")) == str(intern_id) and str(r.get("date", "")) == date_str
            for r in records
        )
    except gspread.WorksheetNotFound:
        return False


def get_checkins_for_week(iso_week: int, year: int) -> list[CheckIn]:
    ss = _get_spreadsheet()
    sheet_name = checkin_sheet_name(iso_week, year)
    try:
        ws = _with_sheets_retry(lambda: ss.worksheet(sheet_name))
    except gspread.WorksheetNotFound:
        return []
    records = _with_sheets_retry(ws.get_all_records)
    checkins = []
    for r in records:
        try:
            checkins.append(CheckIn(
                date=date.fromisoformat(str(r["date"])),
                intern_id=str(r["intern_id"]),
                telegram_user_id=int(r["telegram_user_id"]),
                full_name=str(r["full_name"]),
                checkin_timestamp_utc=datetime.fromisoformat(str(r["checkin_timestamp_utc"])),
                checkin_timestamp_edt=datetime.fromisoformat(str(r["checkin_timestamp_edt"])),
                message_text=str(r.get("message_text", "")),
                message_id=int(r["message_id"]),
                validated=str(r.get("validated", "True")).upper() in ("TRUE", "1"),
                late=str(r.get("late", "False")).upper() in ("TRUE", "1"),
                week_number=int(r["week_number"]),
            ))
        except Exception:
            continue
    return checkins


def get_config() -> Config:
    global _config_cache
    if _config_cache and _cache_fresh(_config_cache[0]):
        return _config_cache[1]

    ss = _get_spreadsheet()
    ws = _with_sheets_retry(lambda: ss.worksheet("CONFIG"))
    records = _with_sheets_retry(ws.get_all_records)
    kv = {r["key"]: str(r["value"]) for r in records if r.get("key")}

    def _int_or(key, default):
        v = kv.get(key, "").strip()
        try:
            return int(v) if v else default
        except (ValueError, TypeError):
            return default

    def _float_or(key, default):
        v = kv.get(key, "").strip()
        try:
            return float(v) if v else default
        except (ValueError, TypeError):
            return default

    # Fall back to env vars for critical runtime values if CONFIG sheet is empty
    group_chat_id = _int_or("group_chat_id", None)
    if not group_chat_id and os.environ.get("TELEGRAM_GROUP_CHAT_ID"):
        group_chat_id = int(os.environ["TELEGRAM_GROUP_CHAT_ID"])

    admin_telegram_id = _int_or("admin_telegram_id", None)
    if not admin_telegram_id and os.environ.get("ADMIN_TELEGRAM_USER_ID"):
        admin_telegram_id = int(os.environ["ADMIN_TELEGRAM_USER_ID"])

    cfg = Config(
        checkin_cutoff_time=kv.get("checkin_cutoff_time", "17:00"),
        morning_reminder_time=kv.get("morning_reminder_time", "09:30"),
        second_reminder_time=kv.get("second_reminder_time", "11:30"),
        dm_nudge_time=kv.get("dm_nudge_time", "13:00"),
        precut_reminder_time=kv.get("precut_reminder_time", "17:45"),
        report_day=_int_or("report_day", 4),
        report_time=kv.get("report_time", "18:00"),
        risk_amber_threshold=_float_or("risk_amber_threshold", 0.70),
        risk_red_threshold=_float_or("risk_red_threshold", 0.50),
        streak_concern_days=_int_or("streak_concern_days", 3),
        retention_weeks=_int_or("retention_weeks", 12),
        admin_telegram_id=admin_telegram_id,
        admin_email=kv.get("admin_email", "minhluan081294@gmail.com"),
        group_chat_id=group_chat_id,
    )
    _config_cache = (time.monotonic(), cfg)
    return cfg


def update_config_key(key: str, value: str) -> None:
    ss = _get_spreadsheet()
    ws = _with_sheets_retry(lambda: ss.worksheet("CONFIG"))
    records = _with_sheets_retry(ws.get_all_records)
    for idx, r in enumerate(records, start=2):  # row 1 is header
        if r.get("key") == key:
            _with_sheets_retry(lambda: ws.update_cell(idx, 2, value))
            _invalidate_config_cache()
            return
    _with_sheets_retry(lambda: ws.append_row([key, value]))
    _invalidate_config_cache()


def write_escalation(escalation: Escalation) -> None:
    ss = _get_spreadsheet()
    ws = _with_sheets_retry(lambda: ss.worksheet("ESCALATIONS"))
    _with_sheets_retry(lambda: ws.append_row([
        escalation.date.isoformat(),
        escalation.intern_id,
        escalation.trigger,
        escalation.action_taken,
        escalation.resolved_date.isoformat() if escalation.resolved_date else "",
        escalation.notes or "",
    ]))


def get_checkins_for_date(target_date: date) -> list[CheckIn]:
    iso = target_date.isocalendar()
    return [c for c in get_checkins_for_week(iso.week, iso.year) if c.date == target_date]


def deactivate_intern(intern_id: str) -> None:
    ss = _get_spreadsheet()
    ws = _with_sheets_retry(lambda: ss.worksheet("ROSTER"))
    headers = _with_sheets_retry(lambda: ws.row_values(1))
    col = headers.index("active") + 1
    records = _with_sheets_retry(ws.get_all_records)
    for idx, r in enumerate(records, start=2):
        if str(r.get("intern_id")) == intern_id:
            _with_sheets_retry(lambda: ws.update_cell(idx, col, "FALSE"))
            _invalidate_roster_cache()
            return


def list_checkin_sheet_names() -> list[str]:
    ss = _get_spreadsheet()
    return [ws.title for ws in _with_sheets_retry(ss.worksheets) if ws.title.startswith("CHECKINS_")]


def delete_worksheet(title: str) -> None:
    ss = _get_spreadsheet()
    try:
        ws = _with_sheets_retry(lambda: ss.worksheet(title))
        _with_sheets_retry(lambda: ss.del_worksheet(ws))
    except gspread.WorksheetNotFound:
        pass
