from datetime import date, timedelta
from datastore.models import RiskScore, CheckIn, Intern
from utils.time_utils import edt_now, scheduled_weekdays, is_us_public_holiday


def _working_days_in_week(
    iso_week: int,
    year: int,
    allowed_weekdays: set[int] = None,
    as_of: date = None,
    start_date: date = None,
    end_date: date = None,
) -> list[date]:
    """Dates in the given ISO week that fall on the intern's scheduled weekdays.

    allowed_weekdays is a set of ints (0=Mon … 6=Sun). Defaults to Mon–Fri so
    weekday-only interns are scored over 5 days; weekend workers pass their own
    set (which may include 5=Sat / 6=Sun) and are scored over up to 7 days.
    US public holidays are excluded — nobody's expected to check in, so they
    shouldn't count against attendance rate.
    """
    if allowed_weekdays is None:
        allowed_weekdays = {0, 1, 2, 3, 4}
    monday = date.fromisocalendar(year, iso_week, 1)
    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        if d.weekday() not in allowed_weekdays:
            continue
        if start_date is not None and d < start_date:
            continue
        if end_date is not None and d > end_date:
            continue
        if is_us_public_holiday(d):
            continue
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


def weekly_attendance_rate(checkins: list[CheckIn], intern_id: str, working_days) -> float:
    """Fraction of the intern's scheduled days they checked in.

    working_days may be a list of dates (preferred — only check-ins landing on
    scheduled days count) or an int (legacy — total scheduled day count).
    """
    if isinstance(working_days, int):
        if working_days == 0:
            return 0.0
        days_checked = len({c.date for c in checkins if c.intern_id == intern_id and c.validated})
        return min(1.0, days_checked / working_days)

    working_set = set(working_days)
    if not working_set:
        return 0.0
    checked = {c.date for c in checkins if c.intern_id == intern_id and c.validated}
    days_checked = len(checked & working_set)
    return min(1.0, days_checked / len(working_set))


def _attendance_days_for_intern(
    scheduled_days: list[date],
    checked_dates: set[date],
    start_date: date,
    end_date: date,
    as_of: date,
) -> list[date]:
    """Scheduled days plus any actual check-in day.

    Hours are still useful for reminders and expectations, but a real check-in
    should always count as presence even while schedules are being corrected.
    """
    days = {
        d for d in scheduled_days
        if start_date <= d <= end_date and d <= as_of
    }
    days.update(
        d for d in checked_dates
        if start_date <= d <= end_date and d <= as_of
    )
    return sorted(days)


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


def compute_all_risk_scores(iso_week: int, year: int, as_of: date = None) -> list[RiskScore]:
    """Optimised: pre-fetches 4 weeks of data in bulk to minimise Sheets API calls."""
    from datastore import sheets

    all_interns = sheets.get_all_interns()
    active = [i for i in all_interns if i.active]
    if not active:
        return []

    now = as_of or edt_now().date()

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
        # Start with scheduled workdays, then include actual check-in days even
        # when the stored schedule is stale or wrong.
        allowed = scheduled_weekdays(intern)
        scheduled_days = _working_days_in_week(
            iso_week,
            year,
            allowed,
            as_of=now,
            start_date=intern.start_date,
            end_date=intern.end_date,
        )
        current_checked = get_checked_dates(intern.intern_id, current_key)
        working_days = _attendance_days_for_intern(
            scheduled_days,
            current_checked,
            intern.start_date,
            intern.end_date,
            now,
        )

        # WAR — only check-ins on scheduled days count
        war = weekly_attendance_rate(current_week_checkins, intern.intern_id, working_days)

        # RAR — using pre-fetched cache
        total_days = 0
        checked_days = 0
        for w in range(4):
            ref_date = now - timedelta(weeks=w)
            ref_iso = ref_date.isocalendar()
            key = (ref_iso.week, ref_iso.year)
            scheduled = _working_days_in_week(
                ref_iso.week,
                ref_iso.year,
                allowed,
                as_of=now,
                start_date=intern.start_date,
                end_date=intern.end_date,
            )
            checked = get_checked_dates(intern.intern_id, key)
            attendance_days = _attendance_days_for_intern(
                scheduled,
                checked,
                intern.start_date,
                intern.end_date,
                now,
            )
            checked_days += len({d for d in attendance_days if d in checked})
            total_days += len(attendance_days)
        rar = checked_days / total_days if total_days > 0 else 0.0

        # CAS — consecutive absences over scheduled days only
        cas = 0
        d = now - timedelta(days=1)
        cutoff = now - timedelta(weeks=4)
        while cas < 20 and d >= cutoff:
            if d.weekday() not in allowed:
                d -= timedelta(days=1)
                continue
            if is_us_public_holiday(d):
                d -= timedelta(days=1)
                continue
            if d < intern.start_date or d > intern.end_date:
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
