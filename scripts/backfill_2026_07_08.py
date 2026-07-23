"""Backfill missed check-ins for 2026-07-08: validator bug (online\\s*(?:\\d|...)) failed
to match multi-digit times like 'online 11-2pm' and 'Online 11-3pm'.
Times taken from Telegram message timestamps in bot log.
"""
import os, sys
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent))

EDT = timezone(timedelta(hours=-4))

BACKFILL = [
    ("vashrith_vinodh", datetime(2026, 7, 8, 10, 44, 28, tzinfo=EDT)),
    ("sydney_hall",     datetime(2026, 7, 8, 10, 44, 51, tzinfo=EDT)),
]

from datastore import sheets
from datastore.models import CheckIn
from utils.time_utils import is_late, iso_week

interns = {i.intern_id: i for i in sheets.get_all_interns()}

for intern_id, ts_edt in BACKFILL:
    intern = interns.get(intern_id)
    if not intern:
        print(f"NOT FOUND: {intern_id}")
        continue

    ts_utc = ts_edt.astimezone(timezone.utc)
    work_date = ts_edt.date()
    week, year = iso_week(ts_edt)
    sheet_name = sheets.checkin_sheet_name(week, year)
    fake_msg_id = int(ts_edt.timestamp()) * 1000 + hash(intern_id) % 1000

    if sheets.checkin_exists(fake_msg_id, sheet_name):
        print(f"ALREADY EXISTS: {intern_id}")
        continue

    if sheets.intern_checked_in_today(intern_id, work_date, sheet_name):
        print(f"ALREADY CHECKED IN TODAY: {intern_id}")
        continue

    late_flag = is_late(intern, ts_edt)
    checkin = CheckIn(
        date=work_date,
        intern_id=intern_id,
        telegram_user_id=intern.telegram_user_id,
        full_name=intern.full_name,
        checkin_timestamp_utc=ts_utc,
        checkin_timestamp_edt=ts_edt,
        message_text="[backfill — validator missed 'online HH-HHpm' format]",
        message_id=fake_msg_id,
        validated=True,
        late=late_flag,
        week_number=week,
    )
    sheets.write_checkin(checkin)
    print(f"RECORDED: {intern.full_name} at {ts_edt.strftime('%H:%M')} EDT, late={late_flag}")
