"""One-off: send the morning reminder immediately."""
import os, sys, asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Bot
from datastore.sheets import get_config
from bot.templates import morning_reminder

async def main():
    cfg = get_config()
    text = morning_reminder(cfg.checkin_cutoff_time)
    async with Bot(token=os.environ["TELEGRAM_BOT_TOKEN"]) as bot:
        await bot.send_message(chat_id=cfg.group_chat_id, text=text)
    with open("/tmp/mr_result.txt", "w") as f:
        f.write(f"Sent to group {cfg.group_chat_id}\n")

asyncio.run(main())
