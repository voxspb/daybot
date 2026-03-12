from telegram import ReplyKeyboardMarkup
from telegram.ext import MessageHandler, filters


async def show_menu(update, context):

    keyboard = [
        ["📊 Dashboard", "📋 Сегодня"],
        ["🍽 Питание", "💸 Финансы"],
        ["👨‍👩‍👧 Семья"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "Главное меню",
        reply_markup=reply_markup
    )


def register_menu(app):

    app.add_handler(
        MessageHandler(filters.Regex("^📊 Dashboard$"), show_menu)
    )

    app.add_handler(
        MessageHandler(filters.Regex("^📋 Сегодня$"), show_menu)
    )

    app.add_handler(
        MessageHandler(filters.Regex("^🍽 Питание$"), show_menu)
    )

    app.add_handler(
        MessageHandler(filters.Regex("^💸 Финансы$"), show_menu)
    )

    app.add_handler(
        MessageHandler(filters.Regex("^👨‍👩‍👧 Семья$"), show_menu)
    )