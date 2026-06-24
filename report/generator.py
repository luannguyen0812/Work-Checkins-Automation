from datetime import date
import openpyxl
from datastore.models import RiskScore, CheckIn


def generate_report(iso_week: int, year: int) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    _build_executive_summary(wb, iso_week, year)
    _build_raw_checkins(wb, iso_week, year)
    _build_attendance_rates(wb, iso_week, year)
    _build_trend_lines(wb, iso_week, year)
    _build_heatmap(wb, iso_week, year)
    _build_streaks(wb, iso_week, year)
    _build_risk_scores(wb, iso_week, year)

    from io import BytesIO
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_executive_summary(wb, iso_week: int, year: int) -> None:
    raise NotImplementedError


def _build_raw_checkins(wb, iso_week: int, year: int) -> None:
    raise NotImplementedError


def _build_attendance_rates(wb, iso_week: int, year: int) -> None:
    raise NotImplementedError


def _build_trend_lines(wb, iso_week: int, year: int) -> None:
    raise NotImplementedError


def _build_heatmap(wb, iso_week: int, year: int) -> None:
    raise NotImplementedError


def _build_streaks(wb, iso_week: int, year: int) -> None:
    raise NotImplementedError


def _build_risk_scores(wb, iso_week: int, year: int) -> None:
    raise NotImplementedError


def report_filename(iso_week: int, year: int, gen_date: date) -> str:
    return f"InternAttendance_W{iso_week:02d}_{gen_date.isoformat()}.xlsx"
