import os
from datetime import datetime, timezone

from notion_client import Client
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DB_ID = os.environ["NOTION_DB_ID"]

PUBLIC_URL = os.environ.get("PUBLIC_URL")
PORT = int(os.environ.get("PORT", "10000"))

notion = Client(auth=NOTION_TOKEN)


def create_task_in_notion(title: str, description: str | None = None):
    props = {
        "Task name": {"title": [{"text": {"content": title[:200] or "New task"}}]},
        "Updated at": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
    }
    if description:
        props["Description"] = {"rich_text": [{"text": {"content": description}}]}
    notion.pages.create(parent={"database_id": NOTION_DB_ID}, properties=props)


async def start_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Надішли: Назва | Опис (можна без опису)")


async def any_text(update: Update, _: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    title, desc = text, None
    if "|" in text:
        title, _, desc = text.partition("|")
        title, desc = title.strip(), (desc or "").strip() or None
    try:
        create_task_in_notion(title, desc)
        await update.message.reply_text("✅ Створено в Notion")
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка: {e}")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_text))

    if PUBLIC_URL:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=f"{PUBLIC_URL}/{TELEGRAM_TOKEN}",
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        app.bot.delete_webhook(drop_pending_updates=True)
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )


if __name__ == "__main__":
    main()
