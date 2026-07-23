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
    try:
        msg = update.message
        if not msg or not msg.text:
            return

        if not is_checkin(msg.text):
            logger.info(
                "Validator miss",
                extra={
                    "telegram_user_id": getattr(msg.from_user, "id", None),
                    "telegram_name": " ".join(
                        p for p in [
                            getattr(msg.from_user, "first_name", None),
                            getattr(msg.from_user, "last_name", None),
                        ] if p
                    ),
                    "message_text": msg.text[:200],
                    "chat_id": msg.chat_id,
                },
            )
            return

        cfg = sheets.get_config()
        sender = msg.from_user
        sender_name = " ".join(
            part for part in [
                getattr(sender, "first_name", None),
                getattr(sender, "last_name", None),
            ] if part
        )
        log_extra = {
            "actual_chat_id": msg.chat_id,
            "configured_chat_id": cfg.group_chat_id,
            "telegram_user_id": sender.id,
            "telegram_username": getattr(sender, "username", None),
            "telegram_name": sender_name,
            "message_id": msg.message_id,
        }
        logger.info("Incoming check-in candidate", extra=log_extra)
        if str(msg.chat_id) != str(cfg.group_chat_id):
            logger.info("Check-in ignored: wrong chat", extra=log_extra)
            return

        now_utc = msg.date  # timezone-aware UTC from Telegram
        now_edt = utc_to_edt(now_utc)

        def write_unmatched(reason: str) -> None:
            sheets.write_unmatched_checkin(
                reason=reason,
                telegram_user_id=sender.id,
                telegram_username=getattr(sender, "username", None),
                telegram_name=sender_name,
                chat_id=msg.chat_id,
                message_id=msg.message_id,
                timestamp_utc=now_utc,
                timestamp_edt=now_edt,
                message_text=msg.text,
            )

        user_id = msg.from_user.id
        intern = sheets.get_intern_by_telegram_id(user_id)

        if intern is None:
            logger.info("Check-in ignored: unrecognised Telegram user", extra=log_extra)
            write_unmatched("unrecognised_telegram_user")
            return  # private bot — no DM to unknown users

        work_date = get_work_date(intern, now_edt)

        if not (intern.start_date <= work_date <= intern.end_date):
            logger.info("Check-in ignored: outside intern date range", extra={**log_extra, "intern_id": intern.intern_id})
            write_unmatched("outside_intern_date_range")
            return

        week, year = iso_week(now_edt)
        sheet_name = sheets.checkin_sheet_name(week, year)

        if sheets.checkin_exists(msg.message_id, sheet_name):
            logger.info("Check-in ignored: duplicate message", extra={**log_extra, "intern_id": intern.intern_id})
            return

        if sheets.intern_checked_in_today(intern.intern_id, work_date, sheet_name):
            logger.info("Check-in ignored: already checked in today", extra={**log_extra, "intern_id": intern.intern_id})
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
    except Exception:
        logger.exception("Check-in handler failed")


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
