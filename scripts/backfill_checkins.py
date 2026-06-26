"""Backfill missed check-ins for 2026-06-26 morning (bot lacked admin access).
Marvin checked in at 6:51 AM per Luan; Xinren/Caleb/Steve approximate times
based on order reported. Luan is program manager — skip if not in intern roster.
"""
import os, sys
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

EDT = timezone(timedelta(hours=-4))

# Approximate check-in times (EDT) based on order Luan reported
BACKFILL = [
    ("luan_nguyen",    datetime(2026, 6, 26, 7, 55, tzinfo=EDT)),
]

from datastore import sheets
from datastore.models import CheckIn
from utils.time_utils import is_late, iso_week

interns = {i.intern_id: i for i in sheets.get_all_interns()}
results = []

for intern_id, ts_edt in BACKFILL:
    intern = interns.get(intern_id)
    if not intern:
        results.append(f"NOT FOUND: {intern_id}")
        continue

    ts_utc = ts_edt.astimezone(timezone.utc)
    work_date = ts_edt.date()
    week, year = iso_week(ts_edt)
    sheet_name = sheets.checkin_sheet_name(week, year)
    fake_msg_id = int(ts_edt.timestamp()) * 1000 + hash(intern_id) % 1000

    if sheets.checkin_exists(fake_msg_id, sheet_name):
        results.append(f"ALREADY EXISTS: {intern_id}")
        continue

    late_flag = is_late(intern, ts_edt)
    checkin = CheckIn(
        date=work_date,
        intern_id=intern_id,
        telegram_user_id=intern.telegram_user_id,
        full_name=intern.full_name,
        checkin_timestamp_utc=ts_utc,
        checkin_timestamp_edt=ts_edt,
        message_text="[manual backfill - missed due to bot admin issue]",
        message_id=fake_msg_id,
        validated=True,
        late=late_flag,
        week_number=week,
    )
    sheets.write_checkin(checkin)
    results.append(f"RECORDED: {intern.full_name} at {ts_edt.strftime('%H:%M')} EDT, late={late_flag}")

with open("/tmp/backfill_results.txt", "w") as f:
    f.write("\n".join(results) + "\n")
