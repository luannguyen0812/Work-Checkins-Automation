from datetime import datetime, time
import pytz

EDT = pytz.timezone("America/New_York")
UTC = pytz.utc


def utc_to_edt(dt_utc: datetime) -> datetime:
    return dt_utc.replace(tzinfo=UTC).astimezone(EDT)


def edt_now() -> datetime:
    return datetime.now(EDT)


def is_late(dt_edt: datetime, cutoff_time_str: str = "17:00") -> bool:
    h, m = map(int, cutoff_time_str.split(":"))
    cutoff = dt_edt.replace(hour=h, minute=m, second=0, microsecond=0)
    return dt_edt > cutoff


def iso_week(dt: datetime) -> tuple[int, int]:
    iso = dt.isocalendar()
    return iso.week, iso.year
