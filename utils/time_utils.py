import json
from datetime import datetime, date, timedelta
from typing import Optional, TYPE_CHECKING
import pytz


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence (1-based) of weekday (0=Mon) in the given month."""
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    return first + timedelta(days=delta + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last occurrence of weekday (0=Mon) in the given month."""
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    delta = (last.weekday() - weekday) % 7
    return last - timedelta(days=delta)


def _observed(d: date) -> date:
    """Shift a fixed holiday to its observed date (Fri if Sat, Mon if Sun)."""
    if d.weekday() == 5:  # Saturday
        return d - timedelta(days=1)
    if d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d


def _us_federal_holidays(year: int) -> set[date]:
    return {
        _observed(date(year, 1, 1)),                        # New Year's Day
        _nth_weekday(year, 1, 0, 3),                        # MLK Day (3rd Mon Jan)
        _nth_weekday(year, 2, 0, 3),                        # Presidents' Day (3rd Mon Feb)
        _last_weekday(year, 5, 0),                          # Memorial Day (last Mon May)
        _observed(date(year, 6, 19)),                       # Juneteenth
        _observed(date(year, 7, 4)),                        # Independence Day
        _nth_weekday(year, 9, 0, 1),                        # Labor Day (1st Mon Sep)
        _nth_weekday(year, 10, 0, 2),                       # Columbus Day (2nd Mon Oct)
        _observed(date(year, 11, 11)),                      # Veterans Day
        _nth_weekday(year, 11, 3, 4),                       # Thanksgiving (4th Thu Nov)
        _observed(date(year, 12, 25)),                      # Christmas Day
    }


def is_us_public_holiday(d: date) -> bool:
    """Return True if d is a US federal public holiday (observed date)."""
    return d in _us_federal_holidays(d.year)

if TYPE_CHECKING:
    from datastore.models import Intern

EDT = pytz.timezone("America/New_York")
UTC = pytz.utc

_DAY_MAP = {
    "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6,
}

LATE_GRACE_MINUTES = 30  # minutes after shift start before a check-in is flagged late


def utc_to_edt(dt_utc: datetime) -> datetime:
    return dt_utc.replace(tzinfo=UTC).astimezone(EDT)


def edt_now() -> datetime:
    return datetime.now(EDT)


def iso_week(dt: datetime) -> tuple[int, int]:
    iso = dt.isocalendar()
    return iso.week, iso.year


def _parse_schedule(intern: "Intern") -> list[dict]:
    if not intern.schedule_json:
        return []
    try:
        return json.loads(intern.schedule_json)
    except (json.JSONDecodeError, TypeError):
        return []


def _segment_for_weekday(segments: list[dict], weekday: int) -> Optional[dict]:
    """Return first segment covering weekday (0=Mon … 6=Sun), or None."""
    for seg in segments:
        for day_name in seg.get("days", []):
            if _DAY_MAP.get(day_name) == weekday:
                return seg
    return None


def get_work_date(intern: "Intern", now_edt: datetime) -> date:
    """
    Return the logical work date for a check-in.
    Handles midnight-crossing shifts: if now is before the shift end,
    the work date is yesterday.
    """
    segments = _parse_schedule(intern)
    today = now_edt.date()

    if not segments:
        return today

    seg_today = _segment_for_weekday(segments, today.weekday())
    if seg_today:
        start_h, start_m = map(int, seg_today["start"].split(":"))
        end_h, end_m = map(int, seg_today["end"].split(":"))
        crosses_midnight = (end_h, end_m) < (start_h, start_m)
        if crosses_midnight:
            end_dt = now_edt.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
            if now_edt <= end_dt:
                return today - timedelta(days=1)
        return today

    # Not scheduled today — check if yesterday's midnight-crossing shift spills into now
    yesterday = today - timedelta(days=1)
    seg_yesterday = _segment_for_weekday(segments, yesterday.weekday())
    if seg_yesterday:
        start_h, start_m = map(int, seg_yesterday["start"].split(":"))
        end_h, end_m = map(int, seg_yesterday["end"].split(":"))
        crosses_midnight = (end_h, end_m) < (start_h, start_m)
        if crosses_midnight:
            end_dt = now_edt.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
            if now_edt <= end_dt:
                return yesterday

    return today


def is_working_today(intern: "Intern", now_edt: datetime) -> bool:
    """True if the intern is scheduled on the logical work date."""
    segments = _parse_schedule(intern)
    if not segments:
        return True  # no schedule stored → always accept check-ins
    work_date = get_work_date(intern, now_edt)
    return _segment_for_weekday(segments, work_date.weekday()) is not None


def scheduled_weekdays(intern: "Intern") -> set[int]:
    """
    Set of weekday ints (0=Mon … 6=Sun) the intern is scheduled to work.
    Falls back to Mon–Fri when no schedule is stored, so attendance for
    weekday-only interns is scored over 5 days and weekend workers over their
    actual scheduled days (which may span all 7).
    """
    segments = _parse_schedule(intern)
    if not segments:
        return {0, 1, 2, 3, 4}
    days: set[int] = set()
    for seg in segments:
        for day_name in seg.get("days", []):
            wd = _DAY_MAP.get(day_name)
            if wd is not None:
                days.add(wd)
    return days or {0, 1, 2, 3, 4}


def is_late(intern_or_cutoff, now_edt: datetime) -> bool:
    """
    Per-intern: late if checked in more than LATE_GRACE_MINUTES after shift start.
    Accepts a plain "HH:MM" string for backward compatibility with old call sites.
    """
    if isinstance(intern_or_cutoff, str):
        # Legacy: is_late("17:00", now_edt) — note arg order flip handled in handlers.py
        h, m = map(int, intern_or_cutoff.split(":"))
        cutoff = now_edt.replace(hour=h, minute=m, second=0, microsecond=0)
        return now_edt > cutoff

    intern = intern_or_cutoff
    segments = _parse_schedule(intern)
    if not segments:
        return False  # no schedule → never flag late

    work_date = get_work_date(intern, now_edt)
    seg = _segment_for_weekday(segments, work_date.weekday())
    if not seg:
        return False

    start_h, start_m = map(int, seg["start"].split(":"))
    shift_start = now_edt.replace(hour=start_h, minute=start_m, second=0, microsecond=0)

    # Shift started on a previous calendar day (midnight-crossing)
    if work_date < now_edt.date():
        shift_start -= timedelta(days=1)

    return now_edt > shift_start + timedelta(minutes=LATE_GRACE_MINUTES)
