from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import MessageHandler, ContextTypes, filters


MAIN_MENU_KEYBOARD = [
    ["🍽 Питание", "💸 Финансы"],
    ["📅 День", "👶 Ася"],
    ["📊 Аналитика"]
]

FINANCE_MENU_KEYBOARD = [
    ["➕ Добавить трату"],
    ["📷 Скан чека"],
    ["📈 Динамика цен"],
    ["⬅️ Назад"]
]


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    reply_markup = ReplyKeyboardMarkup(
        MAIN_MENU_KEYBOARD,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🏠 Главное меню",
        reply_markup=reply_markup
    )


async def show_finance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    reply_markup = ReplyKeyboardMarkup(
        FINANCE_MENU_KEYBOARD,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "💸 Финансы",
        reply_markup=reply_markup
    )


async def finance_add_expense_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await update.message.reply_text(
        "Введи расход в формате:\n"
        "/spend 500 продукты\n\n"
        "или просто сообщением:\n"
        "500 продукты"
    )


async def finance_scan_receipt_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await update.message.reply_text(
        "📷 Отправь фото чека следующим сообщением.\n"
        "Бот сохранит его, а позже мы добавим распознавание товаров."
    )


async def finance_price_dynamics_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await update.message.reply_text(
        "📈 Динамика цен — следующий этап.\n"
        "Сначала подключим сохранение чеков и товаров, потом построим статистику."
    )


def register_menu(app):
    app.add_handler(MessageHandler(filters.Regex("^🏠 Главное меню$"), show_main_menu))
    app.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$"), show_main_menu))

    app.add_handler(MessageHandler(filters.Regex("^💸 Финансы$"), show_finance_menu))

    app.add_handler(
        MessageHandler(filters.Regex("^➕ Добавить трату$"), finance_add_expense_hint)
    )

    app.add_handler(
        MessageHandler(filters.Regex("^📷 Скан чека$"), finance_scan_receipt_hint)
    )

    app.add_handler(
        MessageHandler(filters.Regex("^📈 Динамика цен$"), finance_price_dynamics_hint)
    )