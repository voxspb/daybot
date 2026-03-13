import os
import re
import pytesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
from PIL import Image

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

def extract_total(text: str):
    text = text.upper()

    patterns = [
        r"(ИТОГО|ИТОГ|TOTAL|SUM)[^\d]*(\d+[.,]\d{2})",
        r"(К ОПЛАТЕ)[^\d]*(\d+[.,]\d{2})"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(2).replace(",", "."))

    return None

async def start_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for_receipt"] = True
    await update.message.reply_text("📷 Отправьте фотографию чека.")

async def scan_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_for_receipt"):
    return

    photo = update.message.photo[-1]
    file = await photo.get_file()

    os.makedirs("receipts", exist_ok=True)

    file_path = f"receipts/{photo.file_id}.jpg"
    await file.download_to_drive(file_path)

    # OCR распознавание
    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image, lang="rus+eng", config="--psm 6")
    except Exception as e:
        text = f"OCR ошибка: {e}"

    total = extract_total(text)

    cursor.execute(
        "INSERT INTO receipts (date, photo) VALUES (?, ?)",
        (update.message.date.strftime("%Y-%m-%d"), file_path)
    )
    conn.commit()

    if total:
        cursor.execute(
            "INSERT INTO expenses (amount, category, comment) VALUES (?, ?, ?)",
            (total, "Чек", "Автоматически из OCR")
        )
        conn.commit()

        context.user_data["waiting_for_receipt"] = False

        await update.message.reply_text(
            f"📷 Чек сохранён\n\n💰 Найдена сумма: {total}"
        )

    else:
        context.user_data["waiting_for_receipt"] = False
        context.user_data["waiting_for_amount"] = True
        await update.message.reply_text(
            f"📷 Чек сохранён\n\nСумму определить не удалось.\nВведите сумму чека:"
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

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, manual_amount)
    )

async def manual_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not context.user_data.get("waiting_for_amount"):
        return

    try:
        amount = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Введите сумму числом.")
        return

    cursor.execute(
        "INSERT INTO expenses (amount, category, comment) VALUES (?, ?, ?)",
        (amount, "Чек", "Введено вручную")
    )
    conn.commit()

    context.user_data["waiting_for_amount"] = False

    await update.message.reply_text(f"💰 Сумма {amount} добавлена.")

def get_sum():
    return 0


def fmt_money(value):
    return f"{value:.2f}"