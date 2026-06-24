from telegram import Update
from telegram.ext import ContextTypes
from bot.validator import is_checkin
from datastore import sheets
from utils.logger import get_logger

logger = get_logger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return

    cfg = sheets.get_config()
    if str(msg.chat_id) != str(cfg.group_chat_id):
        return

    user_id = msg.from_user.id
    intern = sheets.get_intern_by_telegram_id(user_id)

    if not is_checkin(msg.text):
        return

    if intern is None:
        logger.debug("Unrecognised user attempted check-in", extra={"telegram_user_id": user_id})
        from bot.templates import unknown_user_attempt
        await context.bot.send_message(chat_id=user_id, text=unknown_user_attempt())
        return

    raise NotImplementedError("write CheckIn record, dedup by message_id, mark late flag")


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass
