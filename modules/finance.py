import os
from database import cursor, conn
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


async def scan_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):

    photo = update.message.photo[-1]
    file = await photo.get_file()

    os.makedirs("receipts", exist_ok=True)

    file_path = f"receipts/{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    cursor.execute(
        "INSERT INTO receipts (date, photo) VALUES (?, ?)",
        (update.message.date.strftime("%Y-%m-%d"), file_path)
    )
    conn.commit()

    await update.message.reply_text(
        "📷 Чек сохранён.\n\nПозже добавим распознавание."
    )


def register_finance(app):

    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex("Финансы"),
            finance_menu
        )
    )

    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            scan_receipt
        )
    )


def get_sum():
    return 0


def fmt_money(value):
    return f"{value:.2f}"