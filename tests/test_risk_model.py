import pytest
from datastore.models import Intern
from datastore.queries import compute_risk_score
from datetime import date


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
