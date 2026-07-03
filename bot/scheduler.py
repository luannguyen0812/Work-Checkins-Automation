import asyncio
from datetime import date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from utils.logger import get_logger
from utils.time_utils import edt_now, get_work_date, is_working_today, is_us_public_holiday, _parse_schedule, _segment_for_weekday

logger = get_logger(__name__)

# Set by main.py's post_init hook once the bot's event loop is running
_bot_loop: asyncio.AbstractEventLoop | None = None

# Tracks interns nudged today; reset each calendar day
_nudged_today: set[str] = set()
_nudge_date: date | None = None


TZ = "America/New_York"


def _hm(t: str) -> tuple[int, int]:
    """Parse 'HH:MM' into (hour, minute)."""
    h, m = t.split(":")
    return int(h), int(m)


def register_jobs(bot) -> BackgroundScheduler:
    from datastore.sheets import get_config
    cfg = get_config()

    scheduler = BackgroundScheduler(timezone=TZ)

    # NOTE: day_of_week uses APScheduler day-name strings ('mon-fri'), NOT
    # numeric crontab. CronTrigger.from_crontab does not remap crontab's
    # 0=Sun/1=Mon numbering, so a numeric '1-5' is read as Tue–Sat — which
    # wrongly fired reminders on Saturday and skipped Monday. Day names are
    # unambiguous. Check-in reminders are weekday-only; weekend check-ins are
    # still captured silently, just never nudged.
    mh, mm = _hm(cfg.morning_reminder_time)
    sh, sm = _hm(cfg.second_reminder_time)
    ph, pm = _hm(cfg.precut_reminder_time)

    jobs = [
        ("morning_reminder", CronTrigger(day_of_week="mon-fri", hour=mh, minute=mm, timezone=TZ), _send_morning_reminder),
        ("second_reminder",  CronTrigger(day_of_week="mon-fri", hour=sh, minute=sm, timezone=TZ), _send_second_reminder),
        ("precut_reminder",  CronTrigger(day_of_week="mon-fri", hour=ph, minute=pm, timezone=TZ), _send_precut_reminder),
        ("dm_nudge",         CronTrigger(day_of_week="mon-fri", hour="8-22", minute="*/30", timezone=TZ), _send_dm_nudges),
        ("weekly_report",    CronTrigger(day_of_week="mon", hour=9, minute=30, timezone=TZ), _generate_and_send_report),
        ("data_retention",   CronTrigger(day_of_week="sun", hour=2, minute=0, timezone=TZ), _run_retention_cleanup),
    ]

    for job_id, trigger, fn in jobs:
        scheduler.add_job(
            fn,
            trigger,
            id=job_id,
            replace_existing=True,
            kwargs={"bot": bot},
        )

    return scheduler


def _run_async(coro) -> None:
    """Submit a coroutine to the bot's event loop from a background scheduler thread."""
    if _bot_loop is not None and _bot_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, _bot_loop)
        future.result(timeout=30)
    else:
        # Fallback before the loop is captured (shouldn't happen in practice)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()


def _send_morning_reminder(bot) -> None:
    from datastore.sheets import get_config
    from bot.templates import morning_reminder
    try:
        today = edt_now().date()
        if is_us_public_holiday(today):
            logger.info("Skipping morning reminder — US public holiday", extra={"date": str(today)})
            return
        cfg = get_config()
        if not cfg.group_chat_id:
            logger.warning("group_chat_id not set — skipping morning reminder")
            return
        text = morning_reminder(cfg.checkin_cutoff_time)
        _run_async(bot.send_message(chat_id=cfg.group_chat_id, text=text))
        logger.info("Morning reminder sent")
    except Exception:
        logger.exception("Failed to send morning reminder")


def _send_second_reminder(bot) -> None:
    from datastore.sheets import get_config
    from bot.templates import second_reminder
    try:
        today = edt_now().date()
        if is_us_public_holiday(today):
            logger.info("Skipping second reminder — US public holiday", extra={"date": str(today)})
            return
        cfg = get_config()
        if not cfg.group_chat_id:
            return
        _run_async(bot.send_message(chat_id=cfg.group_chat_id, text=second_reminder()))
        logger.info("Second reminder sent")
    except Exception:
        logger.exception("Failed to send second reminder")


def _send_precut_reminder(bot) -> None:
    from datastore.sheets import get_config
    from bot.templates import precut_reminder
    try:
        today = edt_now().date()
        if is_us_public_holiday(today):
            logger.info("Skipping pre-cutoff reminder — US public holiday", extra={"date": str(today)})
            return
        cfg = get_config()
        if not cfg.group_chat_id:
            return
        text = precut_reminder(cfg.checkin_cutoff_time, cfg.precut_reminder_time)
        _run_async(bot.send_message(chat_id=cfg.group_chat_id, text=text))
        logger.info("Pre-cutoff reminder sent")
    except Exception:
        logger.exception("Failed to send pre-cutoff reminder")


def _send_dm_nudges(bot) -> None:
    """
    Runs every 30 min Mon–Fri. For each intern whose shift started > 30 min ago
    and who hasn't checked in yet, send one DM nudge per day.
    """
    global _nudged_today, _nudge_date
    from datastore.sheets import get_all_interns
    from datastore.queries import get_todays_checkin_intern_ids
    try:
        now = edt_now()
        today = now.date()

        if is_us_public_holiday(today):
            logger.info("Skipping DM nudges — US public holiday", extra={"date": str(today)})
            return

        # Reset daily nudge tracking at midnight
        if _nudge_date != today:
            _nudged_today = set()
            _nudge_date = today

        interns = [i for i in get_all_interns() if i.active]
        checked_in_ids = get_todays_checkin_intern_ids(today)

        for intern in interns:
            if intern.intern_id in checked_in_ids:
                continue
            if intern.intern_id in _nudged_today:
                continue
            if not (intern.start_date <= today <= intern.end_date):
                continue

            segments = _parse_schedule(intern)
            if segments:
                seg = _segment_for_weekday(segments, today.weekday())
                if not seg:
                    continue  # not scheduled today
                start_h, start_m = map(int, seg["start"].split(":"))
                shift_start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                if now < shift_start + timedelta(minutes=30):
                    continue  # shift hasn't started yet (or still within grace window)
            # No schedule stored: fall through and nudge (conservative)

            if intern.telegram_user_id:
                first_name = intern.full_name.split()[0]
                try:
                    _run_async(bot.send_message(
                        chat_id=intern.telegram_user_id,
                        text=f"Hey {first_name}, don't forget to check in! "
                             f"Send \"I'm online\" in the intern group. 👋",
                    ))
                    _nudged_today.add(intern.intern_id)
                    logger.info("DM nudge sent", extra={"intern_id": intern.intern_id})
                except Exception:
                    logger.warning("DM nudge failed", extra={"intern_id": intern.intern_id})
    except Exception:
        logger.exception("DM nudge job failed")


def _generate_and_send_report(bot) -> None:
    from datetime import timedelta
    from utils.time_utils import edt_now
    from report.generator import generate_report, report_filename
    from report.delivery import send_report_telegram
    from bot.templates import weekly_report_dm
    from datastore.queries import compute_all_risk_scores
    try:
        now = edt_now()
        # Report covers the previous full week (Mon–Sun), which ended yesterday (Sunday)
        last_sunday = now - timedelta(days=now.weekday() + 1)
        iso = last_sunday.isocalendar()
        week, year = iso.week, iso.year

        report_bytes = generate_report(week, year)
        filename = report_filename(week, year, last_sunday)

        scores = compute_all_risk_scores(week, year)
        total = len(scores)
        avg_rate = round(sum(s.war for s in scores) / total * 100, 1) if scores else 0.0
        red = [s for s in scores if s.risk_band == "RED"]
        amber = [s for s in scores if s.risk_band == "AMBER"]

        monday = last_sunday - timedelta(days=6)
        date_range = f"{monday.strftime('%b %d')} – {last_sunday.strftime('%b %d, %Y')}"

        caption = weekly_report_dm(
            week_number=week,
            date_range=date_range,
            total_interns=total,
            avg_rate=avg_rate,
            red_count=len(red),
            red_names=", ".join(s.full_name for s in red) or "None",
            amber_count=len(amber),
            amber_names=", ".join(s.full_name for s in amber) or "None",
            timestamp=now.strftime("%Y-%m-%d %H:%M"),
        )

        _run_async(send_report_telegram(bot, report_bytes, filename, caption))
        logger.info("Weekly report delivered", extra={"week": week, "year": year})
    except Exception:
        logger.exception("Failed to generate/send weekly report")
        _notify_admin_error(bot, "Weekly report generation failed. Check logs.")


def _run_retention_cleanup(bot) -> None:
    from datastore.sheets import get_config, list_checkin_sheet_names, delete_worksheet
    from utils.time_utils import edt_now
    try:
        cfg = get_config()
        now = edt_now().date()
        for name in list_checkin_sheet_names():
            parts = name.split("_")
            if len(parts) != 3:
                continue
            try:
                sheet_year, sheet_week = int(parts[1]), int(parts[2])
                sheet_monday = date.fromisocalendar(sheet_year, sheet_week, 1)
                age_weeks = (now - sheet_monday).days // 7
                if age_weeks > cfg.retention_weeks:
                    delete_worksheet(name)
                    logger.info("Deleted old check-in sheet", extra={"sheet": name})
            except (ValueError, IndexError):
                continue
    except Exception:
        logger.exception("Retention cleanup failed")


def _notify_admin_error(bot, message: str) -> None:
    from datastore.sheets import get_config
    try:
        cfg = get_config()
        if cfg.admin_telegram_id:
            _run_async(bot.send_message(chat_id=cfg.admin_telegram_id, text=f"⚠️ {message}"))
    except Exception:
        logger.exception("Failed to send admin error notification")
