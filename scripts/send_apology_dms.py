"""One-off script: send apology DMs to interns who checked in before the bot had
admin access and were incorrectly nudged as a result."""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from telegram import Bot
from datastore.sheets import get_all_interns

MISSED = {"marvin_nguyen", "xinren_ai", "caleb_berent", "steve_do"}

APOLOGY = (
    "Hey {first_name}, sorry about the nudge earlier! "
    "We had a technical issue with the bot this morning — it wasn't receiving group messages yet. "
    "Your check-in was noted and we've got you covered. Thanks for being on time! ✅"
)


async def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    bot = Bot(token=token)

    interns = {i.intern_id: i for i in get_all_interns()}

    for intern_id in MISSED:
        intern = interns.get(intern_id)
        if not intern:
            print(f"  NOT FOUND in roster: {intern_id}")
            continue
        if not intern.telegram_user_id:
            print(f"  NO TELEGRAM ID: {intern_id}")
            continue
        first_name = intern.full_name.split()[0]
        try:
            await bot.send_message(
                chat_id=intern.telegram_user_id,
                text=APOLOGY.format(first_name=first_name),
            )
            print(f"  Sent to {intern.full_name} ({intern_id})")
        except Exception as e:
            print(f"  FAILED {intern_id}: {e}")


asyncio.run(main())
