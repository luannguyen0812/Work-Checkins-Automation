import os
import logging
import threading
from dotenv import load_dotenv

load_dotenv()

# google-auth 2.55+ attempts a Regional Access Boundary lookup on every credential
# refresh. This org doesn't use GCP data residency, so it always fails with
# FAILED_PRECONDITION. Silence it to keep logs clean.
class _SuppressRAB(logging.Filter):
    def filter(self, record):
        return "Regional Access Boundary" not in record.getMessage()

logging.getLogger("google.auth").addFilter(_SuppressRAB())

from telegram.ext import Application, MessageHandler, filters
from bot.handlers import handle_message, handle_dm_registration
from bot.scheduler import register_jobs
from admin.api import app as flask_app
from utils.logger import get_logger

logger = get_logger(__name__)

_bot_loop = None


def run_flask():
    port = int(os.environ.get("ADMIN_API_PORT", 5050))
    flask_app.run(host="127.0.0.1", port=port, use_reloader=False)


async def _post_init(application):
    """Capture the running event loop so scheduler threads can submit coroutines to it."""
    import asyncio
    import bot.scheduler as sched_module
    sched_module._bot_loop = asyncio.get_running_loop()
    logger.info("Event loop captured for scheduler")


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    application = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .build()
    )

    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_dm_registration))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Register APScheduler jobs
    scheduler = register_jobs(application.bot)
    scheduler.start()
    logger.info("Scheduler started")

    if os.environ.get("FLASK_ENABLED", "true").lower() == "true":
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("Flask admin API started on :5050")

    logger.info("Bot starting")
    application.run_polling()  # sync — manages its own event loop internally


if __name__ == "__main__":
    main()
