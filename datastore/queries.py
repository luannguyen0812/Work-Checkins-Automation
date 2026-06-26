from datetime import date, timedelta
from datastore.models import RiskScore, CheckIn, Intern
from utils.time_utils import edt_now


def _working_days_in_week(iso_week: int, year: int, as_of: date = None) -> list[date]:
    monday = date.fromisocalendar(year, iso_week, 1)
    days = []
    for i in range(5):
        d = monday + timedelta(days=i)
        if as_of is None or d <= as_of:
            days.append(d)
    return days


def compute_risk_score(
    intern: Intern,
    war: float,
    rar: float,
    cas: int,
    lcr: float,
    amber_threshold: float = 0.70,
    red_threshold: float = 0.50,
) -> RiskScore:
    raw = (war * 0.40) + (rar * 0.30) + ((1 - cas / 5) * 0.20) + ((1 - lcr) * 0.10)
    score = max(0.0, min(1.0, raw))

    if score >= 0.85:
        band = "GREEN"
    elif score >= amber_threshold:
        band = "AMBER"
    else:
        band = "RED"

    return RiskScore(
        intern_id=intern.intern_id,
        full_name=intern.full_name,
        war=war,
        rar=rar,
        cas=cas,
        lcr=lcr,
        risk_score=score,
        risk_band=band,
    )


def weekly_attendance_rate(checkins: list[CheckIn], intern_id: str, working_days: int) -> float:
    if working_days == 0:
        return 0.0
    days_checked = len({c.date for c in checkins if c.intern_id == intern_id and c.validated})
    return min(1.0, days_checked / working_days)


def rolling_attendance_rate(intern_id: str, weeks: int = 4) -> float:
    """Standalone version — makes individual Sheets calls per week."""
    from datastore import sheets
    now = edt_now().date()
    total_days = 0
    checked_days = 0
    for w in range(weeks):
        ref_date = now - timedelta(weeks=w)
        ref_iso = ref_date.isocalendar()
        week_checkins = sheets.get_checkins_for_week(ref_iso.week, ref_iso.year)
        working = _working_days_in_week(ref_iso.week, ref_iso.year, as_of=now)
        checked = {c.date for c in week_checkins if c.intern_id == intern_id and c.validated}
        checked_days += len({d for d in working if d in checked})
        total_days += len(working)
    return checked_days / total_days if total_days > 0 else 0.0


def current_consecutive_absences(intern_id: str, as_of: date) -> int:
    """Standalone version — makes individual Sheets calls per week."""
    from datastore import sheets
    streak = 0
    d = as_of - timedelta(days=1)
    cutoff = as_of - timedelta(weeks=4)
    while streak < 20 and d >= cutoff:
        if d.weekday() >= 5:
            d -= timedelta(days=1)
            continue
        d_iso = d.isocalendar()
        week_checkins = sheets.get_checkins_for_week(d_iso.week, d_iso.year)
        had_checkin = any(c.date == d and c.intern_id == intern_id and c.validated for c in week_checkins)
        if had_checkin:
            break
        streak += 1
        d -= timedelta(days=1)
    return streak


def late_checkin_rate(checkins: list[CheckIn], intern_id: str) -> float:
    intern_checkins = [c for c in checkins if c.intern_id == intern_id and c.validated]
    if not intern_checkins:
        return 0.0
    return sum(1 for c in intern_checkins if c.late) / len(intern_checkins)


def get_todays_checkin_intern_ids(today: date) -> set[str]:
    from datastore import sheets
    iso = today.isocalendar()
    checkins = sheets.get_checkins_for_week(iso.week, iso.year)
    return {c.intern_id for c in checkins if c.date == today and c.validated}


def get_non_responders_today(all_interns: list[Intern], todays_checkins: list[CheckIn]) -> list[Intern]:
    checked_ids = {c.intern_id for c in todays_checkins}
    return [i for i in all_interns if i.active and i.intern_id not in checked_ids]


def compute_all_risk_scores(iso_week: int, year: int) -> list[RiskScore]:
    """Optimised: pre-fetches 4 weeks of data in bulk to minimise Sheets API calls."""
    from datastore import sheets

    all_interns = sheets.get_all_interns()
    active = [i for i in all_interns if i.active]
    if not active:
        return []

    now = edt_now().date()
    working_days = _working_days_in_week(iso_week, year, as_of=now)

    # Pre-fetch 4 weeks of check-in data
    weeks_cache: dict[tuple, list[CheckIn]] = {}
    for w in range(4):
        ref_date = now - timedelta(weeks=w)
        ref_iso = ref_date.isocalendar()
        key = (ref_iso.week, ref_iso.year)
        if key not in weeks_cache:
            weeks_cache[key] = sheets.get_checkins_for_week(ref_iso.week, ref_iso.year)

    current_key = (iso_week, year)
    current_week_checkins = weeks_cache.get(current_key, [])

    # Build per-intern checked-date sets across all cached weeks
    def get_checked_dates(intern_id: str, key: tuple) -> set[date]:
        return {c.date for c in weeks_cache.get(key, []) if c.intern_id == intern_id and c.validated}

    scores = []
    for intern in active:
        # WAR
        war = weekly_attendance_rate(current_week_checkins, intern.intern_id, len(working_days))

        # RAR — using pre-fetched cache
        total_days = 0
        checked_days = 0
        for w in range(4):
            ref_date = now - timedelta(weeks=w)
            ref_iso = ref_date.isocalendar()
            key = (ref_iso.week, ref_iso.year)
            wd = _working_days_in_week(ref_iso.week, ref_iso.year, as_of=now)
            checked = get_checked_dates(intern.intern_id, key)
            checked_days += len({d for d in wd if d in checked})
            total_days += len(wd)
        rar = checked_days / total_days if total_days > 0 else 0.0

        # CAS — consecutive absences using cached data
        cas = 0
        d = now - timedelta(days=1)
        cutoff = now - timedelta(weeks=4)
        while cas < 20 and d >= cutoff:
            if d.weekday() >= 5:
                d -= timedelta(days=1)
                continue
            d_iso = d.isocalendar()
            key = (d_iso.week, d_iso.year)
            checked = get_checked_dates(intern.intern_id, key)
            if d in checked:
                break
            cas += 1
            d -= timedelta(days=1)

        # LCR
        lcr = late_checkin_rate(current_week_checkins, intern.intern_id)

        score = compute_risk_score(
            intern, war, rar, cas, lcr,
        )
        scores.append(score)

    return scores
