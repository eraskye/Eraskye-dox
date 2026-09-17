"""
Telegram bot for license generation.
Runs separately from the Flask app.
Requires: TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from database import init_db
from license_manager import create_license, VALID_DURATIONS

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
log = logging.getLogger("cloviss-bot")


def _admin_id() -> int:
    try:
        return int(os.environ.get("ADMIN_TELEGRAM_ID", "0"))
    except ValueError:
        return 0


def _is_admin(update: Update) -> bool:
    aid = _admin_id()
    return aid != 0 and update.effective_user and update.effective_user.id == aid


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "CLOVISS SYSTEM PYDXSN — License Bot\n"
        "Use /help to see available commands."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/start — welcome\n"
        "/help — this message\n"
        "/gen <1|3|7|30> — generate a license (admin only)"
    )


async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /gen <1|3|7|30>")
        return

    try:
        days = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Duration must be 1, 3, 7 or 30.")
        return

    if days not in VALID_DURATIONS:
        await update.message.reply_text("Duration must be 1, 3, 7 or 30.")
        return

    try:
        lic = create_license(days)
    except Exception as e:
        log.exception("license generation failed")
        await update.message.reply_text(f"❌ Failed: {e}")
        return

    await update.message.reply_text(
        f"✅ License generated\n"
        f"Duration: {days} day(s)\n"
        f"Key:\n`{lic['key']}`",
        parse_mode="Markdown",
    )


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    if _admin_id() == 0:
        raise SystemExit("ADMIN_TELEGRAM_ID is not set")

    init_db()

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("gen", cmd_gen))

    log.info("Bot starting, admin id = %s", _admin_id())
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
