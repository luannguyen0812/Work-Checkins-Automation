from datastore import sheets
from utils.logger import get_logger

logger = get_logger(__name__)


def run_retention_cleanup(retention_weeks: int = 12) -> None:
    from datetime import date
    from datastore.sheets import list_checkin_sheet_names, delete_worksheet
    today = date.today()
    for name in list_checkin_sheet_names():
        parts = name.split("_")
        if len(parts) != 3:
            continue
        try:
            sheet_year, sheet_week = int(parts[1]), int(parts[2])
            monday = date.fromisocalendar(sheet_year, sheet_week, 1)
            age_weeks = (today - monday).days // 7
            if age_weeks > retention_weeks:
                delete_worksheet(name)
                logger.info("Deleted old check-in sheet", extra={"sheet": name})
        except (ValueError, IndexError):
            continue


def anonymise_opted_out_intern(intern_id: str) -> None:
    """Replace intern's full_name with [REMOVED] in all CHECKINS sheets."""
    for sheet_name in sheets.list_checkin_sheet_names():
        try:
            ss = sheets._get_spreadsheet()
            ws = ss.worksheet(sheet_name)
            records = ws.get_all_records()
            headers = ws.row_values(1)
            if "intern_id" not in headers or "full_name" not in headers:
                continue
            id_col = headers.index("intern_id") + 1
            name_col = headers.index("full_name") + 1
            for row_idx, r in enumerate(records, start=2):
                if str(r.get("intern_id")) == intern_id:
                    ws.update_cell(row_idx, name_col, "[REMOVED]")
        except Exception:
            logger.exception("Anonymisation failed for sheet %s", sheet_name)
