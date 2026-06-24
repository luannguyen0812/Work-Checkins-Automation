import asyncio
import os
import threading
from dotenv import load_dotenv

load_dotenv()

from telegram.ext import Application, MessageHandler, filters
from bot.handlers import handle_message
from bot.scheduler import build_scheduler
from admin.api import app as flask_app
from utils.logger import get_logger

logger = get_logger(__name__)


def run_flask():
    port = int(os.environ.get("ADMIN_API_PORT", 5050))
    flask_app.run(host="127.0.0.1", port=port, use_reloader=False)


async def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    application = Application.builder().token(token).build()

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    scheduler = build_scheduler(application.bot)
    scheduler.start()
    logger.info("Scheduler started")

    if os.environ.get("FLASK_ENABLED", "true").lower() == "true":
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("Flask admin API started on :5050")

    logger.info("Bot starting")
    await application.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
