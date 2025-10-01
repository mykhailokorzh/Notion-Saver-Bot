import os
from datetime import datetime, timezone

from notion_client import Client
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DB_ID = os.environ["NOTION_DB_ID"]

PUBLIC_URL = os.environ.get("PUBLIC_URL")
PORT = int(os.environ.get("PORT", "8000"))

notion = Client(auth=NOTION_TOKEN)


# -------- Notion helper ----------
def create_task_in_notion(
        title: str,
        description: str | None = None,
        status: str | None = None,
        due_date: str | None = None,
        priority: str | None = None,
        task_types: list[str] | None = None,
):
    props: dict = {
        "Task name": {"title": [{"text": {"content": title[:200] or "New task from Telegram"}}]},
        "Updated at": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
    }
    if description:
        props["Description"] = {"rich_text": [{"text": {"content": description}}]}
    if status:
        props["Status"] = {"status": {"name": status}}
    if due_date:
        props["Due date"] = {"date": {"start": due_date}}
    if priority:
        props["Priority"] = {"select": {"name": priority}}
    if task_types:
        props["Task type"] = {"multi_select": [{"name": t} for t in task_types]}
    notion.pages.create(parent={"database_id": NOTION_DB_ID}, properties=props)


# -------- Conversation states ----------
TITLE, DESCRIPTION = range(2)

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

NEW_BTN_KB = ReplyKeyboardMarkup([["/new"]], resize_keyboard=True)


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! Я створюю задачі у Notion.\n"
        "Натисни /new щоб додати нову задачу або /cancel щоб скасувати.",
        reply_markup=NEW_BTN_KB
    )


async def new_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введи *назву задачі* (або /cancel щоб скасувати):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return TITLE


async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = (update.message.text or "").strip()
    if not title:
        await update.message.reply_text(
            "Назва порожня. Введи, будь ласка, *назву задачі* ще раз:",
            parse_mode="Markdown"
        )
        return TITLE
    context.user_data["title"] = title
    await update.message.reply_text(
        "Дякую! Тепер введи *опис* задачі.\n"
        "Щоб пропустити опис — відправ **один символ** (наприклад, `-`) або слово **skip**.\n"
        "Або /cancel щоб скасувати.",
        parse_mode="Markdown"
    )
    return DESCRIPTION


async def finalize_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text or ""
    txt = raw.strip()

    description = None if (txt.lower() == "skip" or len(txt) == 1) else (txt or None)

    title = context.user_data.get("title", "New task from Telegram")

    try:
        create_task_in_notion(title=title, description=description)
        msg = "✅ Створено в Notion: Tasks Tracker" if description else "✅ Створено в Notion (без опису)"
        await update.message.reply_text(msg, reply_markup=NEW_BTN_KB)
        await update.message.reply_text("Хочеш додати ще? Натисни /new.", reply_markup=NEW_BTN_KB)
    except Exception as e:
        await update.message.reply_text(f"❌ Помилка створення: {e}", reply_markup=NEW_BTN_KB)
        await update.message.reply_text("Можеш спробувати ще раз: /new", reply_markup=NEW_BTN_KB)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 Скасовано. Нічого не створюю.", reply_markup=NEW_BTN_KB)
    await update.message.reply_text("Щоб додати новий запис, натисни /new.", reply_markup=NEW_BTN_KB)
    return ConversationHandler.END


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("new", new_task)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_description)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_create)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="create_task_flow",
        persistent=False,
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CommandHandler("cancel", cancel))

    if PUBLIC_URL:
        print("Starting in WEBHOOK mode")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=f"{PUBLIC_URL}/{TELEGRAM_TOKEN}",
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        print("Starting in POLLING mode")
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )


if __name__ == "__main__":
    main()
