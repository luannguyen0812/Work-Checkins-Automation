from datastore.models import RiskScore
from bot.scheduler import _weekly_attendance_lists


def _score(name: str, war: float, risk_band: str = "AMBER") -> RiskScore:
    return RiskScore(
        intern_id=name.lower().replace(" ", "_"),
        full_name=name,
        war=war,
        rar=0.0,
        cas=0,
        lcr=0.0,
        risk_score=0.0,
        risk_band=risk_band,
    )


def test_weekly_report_caption_lists_attendance_bands_not_composite_risk():
    green_attendance_but_amber_risk = _score("Green Weekly", 1.0, risk_band="AMBER")
    amber_attendance = _score("Amber Weekly", 0.80, risk_band="GREEN")
    red_attendance = _score("Red Weekly", 0.50, risk_band="GREEN")

    red, amber = _weekly_attendance_lists([
        green_attendance_but_amber_risk,
        amber_attendance,
        red_attendance,
    ])

    assert green_attendance_but_amber_risk not in red
    assert green_attendance_but_amber_risk not in amber
    assert amber == [amber_attendance]
    assert red == [red_attendance]
