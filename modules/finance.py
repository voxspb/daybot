from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters


async def finance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        ["➕ Добавить трату"],
        ["📷 Скан чека"],
        ["📈 Динамика цен"],
        ["⬅️ Назад"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "💸 Финансы\n\nВыберите действие:",
        reply_markup=reply_markup
    )


def register_finance(app):

    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("Финансы"),
            finance_menu
        )
    )


def get_sum():
    return 0


def fmt_money(value):
    return f"{value:.2f}"