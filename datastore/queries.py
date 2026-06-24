from datetime import date
from datastore.models import RiskScore, CheckIn, Intern


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

    if score >= amber_threshold:
        band = "GREEN" if score >= 0.85 else "AMBER"
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
    raise NotImplementedError


def rolling_attendance_rate(intern_id: str, weeks: int = 4) -> float:
    raise NotImplementedError


def current_consecutive_absences(intern_id: str, as_of: date) -> int:
    raise NotImplementedError


def late_checkin_rate(checkins: list[CheckIn], intern_id: str) -> float:
    raise NotImplementedError


def get_non_responders_today(all_interns: list[Intern], todays_checkins: list[CheckIn]) -> list[Intern]:
    checked_ids = {c.intern_id for c in todays_checkins}
    return [i for i in all_interns if i.active and i.intern_id not in checked_ids]


def compute_all_risk_scores(iso_week: int, year: int) -> list[RiskScore]:
    raise NotImplementedError
