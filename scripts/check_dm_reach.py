"""Check which active interns the bot cannot reach via DM."""
import sys, asyncio, os
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from telegram import Bot
from datastore.sheets import get_all_interns
from datetime import date

async def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    today = date.today()
    unreachable = []
    reachable = []

    async with Bot(token=token) as bot:
        for intern in get_all_interns():
            if not intern.active:
                continue
            if not (intern.start_date <= today <= intern.end_date):
                continue
            if not intern.telegram_user_id:
                unreachable.append(f"{intern.full_name} (no Telegram ID)")
                continue
            try:
                await bot.get_chat(chat_id=intern.telegram_user_id)
                reachable.append(intern.full_name)
            except Exception:
                unreachable.append(intern.full_name)

    with open("/tmp/dm_reach.txt", "w") as f:
        f.write("CANNOT REACH:\n")
        for n in unreachable:
            f.write(f"  - {n}\n")
        f.write("\nCAN REACH:\n")
        for n in reachable:
            f.write(f"  - {n}\n")

asyncio.run(main())
