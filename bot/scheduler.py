from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def build_scheduler(bot) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="America/New_York")

    jobs = [
        ("morning_reminder",  "30 9 * * 1-5",  _send_morning_reminder),
        ("second_reminder",   "30 11 * * 1-5", _send_second_reminder),
        ("dm_nudge",          "0 13 * * 1-5",  _dm_nonresponders),
        ("precut_reminder",   "45 17 * * 1-5", _send_precut_reminder),
        ("weekly_report",     "0 18 * * 5",    _generate_and_send_report),
        ("data_retention",    "0 2 * * 0",     _run_retention_cleanup),
    ]

    for job_id, cron, fn in jobs:
        scheduler.add_job(
            fn,
            CronTrigger.from_crontab(cron, timezone="America/New_York"),
            id=job_id,
            replace_existing=True,
            kwargs={"bot": bot},
        )

    return scheduler


def _send_morning_reminder(bot) -> None:
    raise NotImplementedError


def _send_second_reminder(bot) -> None:
    raise NotImplementedError


def _dm_nonresponders(bot) -> None:
    raise NotImplementedError


def _send_precut_reminder(bot) -> None:
    raise NotImplementedError


def _generate_and_send_report(bot) -> None:
    raise NotImplementedError


def _run_retention_cleanup(bot) -> None:
    raise NotImplementedError
