from datastore import sheets
from utils.logger import get_logger

logger = get_logger(__name__)


def run_retention_cleanup(retention_weeks: int = 12) -> None:
    raise NotImplementedError("delete CHECKINS_* sheets older than retention_weeks")


def anonymise_opted_out_intern(intern_id: str) -> None:
    raise NotImplementedError("replace full_name with [REMOVED] in all sheets")
