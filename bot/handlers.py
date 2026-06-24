import re
from telegram import Update
from telegram.ext import ContextTypes
from datastore import sheets
from datastore.models import CheckIn
from utils.time_utils import utc_to_edt, is_late
from utils.logger import get_logger

logger = get_logger(__name__)

CHECKIN_REGEX = re.compile(
    r"\b(online|i'?m\s+online|checking\s+in|check\s*[‑\-]?\s*in|present|here|good\s+morning|gm)\b",
    re.IGNORECASE,
)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return

    cfg = sheets.get_config()
    if str(msg.chat_id) != str(cfg.group_chat_id):
        return

    user_id = msg.from_user.id
    intern = sheets.get_intern_by_telegram_id(user_id)

    if not CHECKIN_REGEX.search(msg.text):
        return

    if intern is None:
        logger.debug("Unrecognised user attempted check-in", extra={"telegram_user_id": user_id})
        from bot.templates import unknown_user_attempt
        await context.bot.send_message(chat_id=user_id, text=unknown_user_attempt())
        return

    raise NotImplementedError("write CheckIn record, dedup by message_id, mark late flag")


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass
