# src/tg_bot_italian/polling_bot.py
import os
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

BOT_TOKEN = os.environ["BOT_TOKEN"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ciao! Polling is running ✅")
    # handy: shows you chat id in logs if you run in terminal
    print("chat_id:", update.effective_chat.id)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()  # <-- this is polling

if __name__ == "__main__":
    main()
