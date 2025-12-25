# src/tg_bot_italian/send_buongiorno.py
import os
import asyncio
from telegram import Bot

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.getenv("CHAT_ID")
if not CHAT_ID:
    raise RuntimeError("CHAT_ID is not set. Export it before running.")
CHAT_ID = int(CHAT_ID)

async def _async_send():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="com'è il tempo?")

def main():
    asyncio.run(_async_send())

if __name__ == "__main__":
    main()
