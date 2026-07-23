import pytest
from datastore.models import CheckIn, Intern
from datastore.queries import compute_all_risk_scores, compute_risk_score
from datetime import date, datetime


@pytest.fixture
def sample_intern():
    return Intern(
        intern_id="INT001",
        full_name="Alice Example",
        telegram_user_id=123456,
        cohort="2026-Summer",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
    )


def test_green_risk(sample_intern):
    score = compute_risk_score(sample_intern, war=1.0, rar=1.0, cas=0, lcr=0.0)
    assert score.risk_band == "GREEN"
    assert score.risk_score >= 0.85


def test_amber_risk(sample_intern):
    score = compute_risk_score(sample_intern, war=0.75, rar=0.75, cas=1, lcr=0.1)
    assert score.risk_band in ("AMBER", "GREEN")
    assert score.risk_score >= 0.70


def test_red_risk(sample_intern):
    score = compute_risk_score(sample_intern, war=0.40, rar=0.40, cas=4, lcr=0.5)
    assert score.risk_band == "RED"
    assert score.risk_score < 0.70


def test_score_clamped(sample_intern):
    score = compute_risk_score(sample_intern, war=0.0, rar=0.0, cas=5, lcr=1.0)
    assert score.risk_score >= 0.0
    score = compute_risk_score(sample_intern, war=1.0, rar=1.0, cas=0, lcr=0.0)
    assert score.risk_score <= 1.0


def test_risk_score_ignores_weeks_before_intern_start(monkeypatch):
    intern = Intern(
        intern_id="new_starter",
        full_name="New Starter",
        telegram_user_id=123456,
        cohort="2026-Summer",
        start_date=date(2026, 6, 29),
        end_date=date(2026, 8, 31),
        schedule_json='[{"days":["Mon","Tue","Wed","Thu","Fri"],"start":"09:00","end":"18:00"}]',
    )

    def checkin(day: date) -> CheckIn:
        ts = datetime(day.year, day.month, day.day, 13, 0)
        return CheckIn(
            date=day,
            intern_id=intern.intern_id,
            telegram_user_id=intern.telegram_user_id,
            full_name=intern.full_name,
            checkin_timestamp_utc=ts,
            checkin_timestamp_edt=ts,
            message_text="I'm online",
            message_id=1,
            validated=True,
            late=False,
            week_number=day.isocalendar().week,
        )

    # Week 27, 2026 has Jul 3 as observed Independence Day, so Mon-Thu are the
    # only expected weekdays for a Mon-Fri intern who started Jun 29.
    current_week_checkins = [
        checkin(date(2026, 6, 29)),
        checkin(date(2026, 6, 30)),
        checkin(date(2026, 7, 1)),
        checkin(date(2026, 7, 2)),
    ]

    from datastore import sheets
    import datastore.queries as queries

    monkeypatch.setattr(sheets, "get_all_interns", lambda: [intern])
    monkeypatch.setattr(
        sheets,
        "get_checkins_for_week",
        lambda week, year: current_week_checkins if (week, year) == (27, 2026) else [],
    )
    monkeypatch.setattr(queries, "edt_now", lambda: datetime(2026, 7, 6, 12, 0))

    [score] = compute_all_risk_scores(27, 2026, as_of=date(2026, 7, 5))

    assert score.war == 1.0
    assert score.rar == 1.0
    assert score.risk_band == "GREEN"


def test_risk_score_counts_off_schedule_checkin(monkeypatch):
    intern = Intern(
        intern_id="off_schedule",
        full_name="Off Schedule",
        telegram_user_id=123456,
        cohort="2026-Summer",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
        schedule_json='[{"days":["Wed"],"start":"09:00","end":"18:00"}]',
    )

    monday = date(2026, 6, 22)
    wednesday = date(2026, 6, 24)
    ts = datetime(monday.year, monday.month, monday.day, 13, 0)
    checkin = CheckIn(
        date=monday,
        intern_id=intern.intern_id,
        telegram_user_id=intern.telegram_user_id,
        full_name=intern.full_name,
        checkin_timestamp_utc=ts,
        checkin_timestamp_edt=ts,
        message_text="I'm online",
        message_id=1,
        validated=True,
        late=False,
        week_number=monday.isocalendar().week,
    )

    from datastore import sheets

    monkeypatch.setattr(sheets, "get_all_interns", lambda: [intern])
    monkeypatch.setattr(
        sheets,
        "get_checkins_for_week",
        lambda week, year: [checkin] if (week, year) == (26, 2026) else [],
    )

    [score] = compute_all_risk_scores(26, 2026, as_of=date(2026, 6, 28))

    assert monday.isocalendar().week == wednesday.isocalendar().week
    assert score.war == 0.5
