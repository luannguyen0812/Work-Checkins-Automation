import sys, asyncio, os
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from telegram import Bot

async def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    results = []
    async with Bot(token=token) as bot:
        # Try original ID
        for chat_id in [-5172166288, -1005172166288]:
            try:
                chat = await bot.get_chat(chat_id=chat_id)
                results.append(f"get_chat({chat_id}): OK — title={chat.title!r} type={chat.type}")
            except Exception as e:
                results.append(f"get_chat({chat_id}): {e}")
    with open("/tmp/debug_chat.txt", "w") as f:
        f.write("\n".join(results) + "\n")

asyncio.run(main())
