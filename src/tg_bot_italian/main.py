import os
import json
import uuid
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Tuple

from fastapi import FastAPI, Request, Response
from http import HTTPStatus

from telegram import Update, ForceReply
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PENDING_PATH = DATA_DIR / "pending.json"
LOG_PATH = DATA_DIR / "log.jsonl"
QUESTIONS_PATH = BASE_DIR / "questions.txt"
ANSWERS_PATH = BASE_DIR / "answers.txt"

BOT_TOKEN = os.environ["BOT_TOKEN"]  # set in your server env
WEBHOOK_SECRET_PATH = os.environ.get("WEBHOOK_SECRET_PATH")  # simple secret
# Example webhook URL: https://your-domain.com/webhook/<WEBHOOK_SECRET_PATH>

# ----------------------------
# File helpers (simple + safe)
# ----------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PENDING_PATH.exists():
        PENDING_PATH.write_text(json.dumps({}), encoding="utf-8")
    if not LOG_PATH.exists():
        LOG_PATH.write_text("", encoding="utf-8")

def _load_pending() -> Dict[str, Any]:
    _ensure_data_files()
    try:
        return json.loads(PENDING_PATH.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        # If corrupted, start fresh (PoC behavior).
        return {}

def _save_pending(pending: Dict[str, Any]) -> None:
    _ensure_data_files()
    PENDING_PATH.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")

def _append_log(entry: Dict[str, Any]) -> None:
    _ensure_data_files()
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _load_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines

def _pick_question() -> Tuple[str, str, str]:
    """
    Returns (qid, direction, sentence)
    direction is 'IT' or 'EN'
    """
    raw = _load_lines(QUESTIONS_PATH)
    if not raw:
        return (str(uuid.uuid4()), "EN", "No questions found. Add lines to questions.txt")
    line = random.choice(raw)
    if "|" in line:
        direction, sentence = line.split("|", 1)
        direction = direction.strip().upper()
        sentence = sentence.strip()
    else:
        direction, sentence = "EN", line
    return (str(uuid.uuid4()), direction, sentence)

def _pick_bot_reply() -> str:
    raw = _load_lines(ANSWERS_PATH)
    return random.choice(raw) if raw else "Thanks!"

# ----------------------------
# Core function: ask()
# ----------------------------

async def ask(chat_id: int, user: Dict[str, Any], context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Sends a random question, stores a pending record keyed by the sent message_id.
    """
    qid, direction, sentence = _pick_question()
    prompt = (
        f"📝 Question ID: {qid}\n"
        f"Translate this sentence:\n"
        f"{'🇮🇹 Italian → English' if direction == 'IT' else '🇬🇧 English → Italian'}\n\n"
        f"“{sentence}”\n\n"
        f"Reply *to this message* with your translation."
    )

    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=prompt,
        parse_mode="Markdown",
        reply_markup=ForceReply(selective=True),
    )

    pending = _load_pending()
    pending[str(sent.message_id)] = {
        "qid": qid,
        "direction": direction,
        "sentence": sentence,
        "asked_at": _now_iso(),
        "chat_id": chat_id,
        "user": user,
        "question_message_id": sent.message_id,
    }
    _save_pending(pending)

    _append_log({
        "event": "asked",
        "ts": _now_iso(),
        "qid": qid,
        "direction": direction,
        "sentence": sentence,
        "chat_id": chat_id,
        "user": user,
        "question_message_id": sent.message_id,
    })

# ----------------------------
# Telegram handlers
# ----------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    await update.message.reply_text(
        "Hi! Use /ask to get a translation question.\n"
        "Reply to the question message with your translation."
    )
    # optional: auto-ask first question
    await ask(update.effective_chat.id, _user_meta(u), context)

async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    await ask(update.effective_chat.id, _user_meta(u), context)

def _user_meta(u) -> Dict[str, Any]:
    if not u:
        return {}
    return {
        "user_id": u.id,
        "username": u.username,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "language_code": u.language_code,
    }

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    If the user replies to a question message, match by reply_to_message.message_id.
    Then log answer, send a canned bot reply (PoC), and mark as completed.
    """
    msg = update.message
    if not msg or not msg.text:
        return

    if not msg.reply_to_message:
        # Not a reply to a question; ignore or guide
        return

    replied_id = str(msg.reply_to_message.message_id)
    pending = _load_pending()
    if replied_id not in pending:
        return  # reply to something else

    record = pending.pop(replied_id)
    _save_pending(pending)

    user_answer = msg.text.strip()
    bot_reply = _pick_bot_reply()

    # Send a PoC response (later you replace this with ChatGPT evaluation/correction)
    await msg.reply_text(f"✅ Received.\n\n🤖 {bot_reply}")

    _append_log({
        "event": "answered",
        "ts": _now_iso(),
        "qid": record.get("qid"),
        "direction": record.get("direction"),
        "sentence": record.get("sentence"),
        "asked_at": record.get("asked_at"),
        "answered_at": _now_iso(),
        "chat_id": record.get("chat_id"),
        "user": record.get("user"),
        "question_message_id": record.get("question_message_id"),
        "answer_message_id": msg.message_id,
        "user_answer": user_answer,
        "bot_reply": bot_reply,
    })

def build_telegram_app() -> Application:
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ask", ask_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return application

# ----------------------------
# FastAPI webhook server
# ----------------------------

telegram_app = build_telegram_app()
api = FastAPI()

@api.on_event("startup")
async def on_startup():
    _ensure_data_files()
    await telegram_app.initialize()
    await telegram_app.start()

@api.on_event("shutdown")
async def on_shutdown():
    await telegram_app.stop()
    await telegram_app.shutdown()

@api.post(f"/webhook/{WEBHOOK_SECRET_PATH}")
async def telegram_webhook(request: Request) -> Response:
    data = await request.json()
    update = Update.de_json(data=data, bot=telegram_app.bot)
    await telegram_app.process_update(update)
    return Response(status_code=HTTPStatus.OK)

# Health check
@api.get("/health")
async def health():
    return {"ok": True}


def main():
    mode = os.getenv("MODE", "polling").lower()

    if mode == "polling":
        print("Starting Telegram bot (polling)...")
        app = build_telegram_app()
        app.run_polling()

    elif mode == "webhook":
        if not WEBHOOK_SECRET_PATH:
            raise RuntimeError("WEBHOOK_SECRET_PATH must be set in webhook mode")   
        print("Starting Telegram bot (webhook via uvicorn)...")
        import uvicorn
        port = int(os.getenv("PORT", "8000"))
        uvicorn.run("tg_bot_italian.main:api", host="0.0.0.0", port=port, reload=False)

    else:
        raise RuntimeError("MODE must be 'polling' or 'webhook'")
