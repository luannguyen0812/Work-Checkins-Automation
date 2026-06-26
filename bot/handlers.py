import re
from telegram import Update
from telegram.ext import ContextTypes
from bot.validator import is_checkin
from datastore import sheets
from datastore.models import CheckIn
from utils.logger import get_logger
from utils.time_utils import utc_to_edt, is_late, iso_week, get_work_date, is_working_today

_NAME_PATTERN = re.compile(
    r"(?:hi[\s,!]*)?(?:my\s+name\s+is|i'?m\s+called|i\s+am\s+called|i'?m|i\s+am)\s+"
    r"([A-Za-zÀ-ÖØ-öø-ÿ'\-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ'\-]+)+)",
    re.IGNORECASE,
)

logger = get_logger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return

    cfg = sheets.get_config()
    logger.info("Incoming group msg", extra={"actual_chat_id": msg.chat_id, "configured_chat_id": cfg.group_chat_id})
    if str(msg.chat_id) != str(cfg.group_chat_id):
        return

    if not is_checkin(msg.text):
        return

    user_id = msg.from_user.id
    intern = sheets.get_intern_by_telegram_id(user_id)

    if intern is None:
        logger.debug("Unrecognised user attempted check-in", extra={"telegram_user_id": user_id})
        return  # private bot — no DM to unknown users

    now_utc = msg.date  # timezone-aware UTC from Telegram
    now_edt = utc_to_edt(now_utc)
    work_date = get_work_date(intern, now_edt)

    if not (intern.start_date <= work_date <= intern.end_date):
        logger.debug("Check-in outside intern date range", extra={"intern_id": intern.intern_id})
        return

    week, year = iso_week(now_edt)
    sheet_name = sheets.checkin_sheet_name(week, year)

    if sheets.checkin_exists(msg.message_id, sheet_name):
        logger.debug("Duplicate check-in ignored", extra={"message_id": msg.message_id})
        return

    late_flag = is_late(intern, now_edt)

    checkin = CheckIn(
        date=work_date,
        intern_id=intern.intern_id,
        telegram_user_id=user_id,
        full_name=intern.full_name,
        checkin_timestamp_utc=now_utc,
        checkin_timestamp_edt=now_edt,
        message_text=msg.text[:200],
        message_id=msg.message_id,
        validated=True,
        late=late_flag,
        week_number=week,
    )

    sheets.write_checkin(checkin)
    logger.info("Check-in recorded", extra={"intern_id": intern.intern_id, "late": late_flag})


async def handle_dm_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return

    user_id = msg.from_user.id
    username = msg.from_user.username

    if sheets.is_already_registered(user_id):
        await msg.reply_text("You're already registered! Send your check-ins in the intern group. 👍")
        return

    match = _NAME_PATTERN.search(msg.text)
    if not match:
        await msg.reply_text(
            "Hey! To register for check-ins, send:\n\n"
            "Hi, my name is [Your Full Name]\n\n"
            "Use the same name you registered with."
        )
        return

    name_query = match.group(1).strip()
    member, score = sheets.find_intern_candidate_by_name(name_query)

    if score < 0.75 or member is None:
        await msg.reply_text(
            f'Couldn\'t find "{name_query}" on the roster. '
            "Check the spelling matches your registration name, or contact your program manager."
        )
        logger.info("DM registration: no match", extra={"query": name_query, "score": score})
        return

    sheets.register_intern_from_dm(user_id, username, member)
    first_name = name_query.split()[0]
    await msg.reply_text(
        f"You're all set, {first_name}! ✅\n\n"
        "When your shift starts, send \"I'm online\" or \"checking in\" in the intern group.\n"
        "If you forget, I'll DM you a reminder around 1PM on weekdays."
    )
    logger.info("DM registration: success", extra={"telegram_user_id": user_id, "matched_name": name_query, "score": score})


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass
