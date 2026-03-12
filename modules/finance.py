from datetime import datetime
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters

from database import cursor, conn
from modules.tasks import ensure_allowed


def fmt_money(value: float) -> str:
    return f"{value:.2f}"


def get_sum(query: str, params=()):
    cursor.execute(query, params)
    value = cursor.fetchone()[0]
    return float(value or 0)


async def spend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return

    try:
        if len(context.args) < 2:
            raise ValueError("not enough args")

        amount_raw = context.args[0].replace(",", ".")
        amount = float(amount_raw)

        if amount <= 0:
            raise ValueError("amount <= 0")

        category = context.args[1]
        comment = " ".join(context.args[2:]).strip()

        cursor.execute(
            "INSERT INTO expenses (amount, category, comment, created_at) VALUES (?, ?, ?, ?)",
            (amount, category, comment, datetime.now().isoformat())
        )
        conn.commit()

        text = f"Расход добавлен:\n{fmt_money(amount)} — {category}"
        if comment:
            text += f"\nКомментарий: {comment}"

        await update.message.reply_text(text)

    except Exception:
        await update.message.reply_text(
            "Формат:\n"
            "/spend 500 продукты\n"
            "/spend 120 кофе латте"
        )


async def income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return

    try:
        if len(context.args) < 2:
            raise ValueError("not enough args")

        amount_raw = context.args[0].replace(",", ".")
        amount = float(amount_raw)

        if amount <= 0:
            raise ValueError("amount <= 0")

        source = context.args[1]
        comment = " ".join(context.args[2:]).strip()

        cursor.execute(
            "INSERT INTO incomes (amount, source, comment, created_at) VALUES (?, ?, ?, ?)",
            (amount, source, comment, datetime.now().isoformat())
        )
        conn.commit()

        text = f"Доход добавлен:\n{fmt_money(amount)} — {source}"
        if comment:
            text += f"\nКомментарий: {comment}"

        await update.message.reply_text(text)

    except Exception:
        await update.message.reply_text(
            "Формат:\n"
            "/income 2500 подработка\n"
            "/income 50000 зарплата март"
        )


async def money_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return

    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE date(created_at, 'localtime') = date('now', 'localtime')
        GROUP BY category
        ORDER BY SUM(amount) DESC
    """)
    rows = cursor.fetchall()

    total = get_sum("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE date(created_at, 'localtime') = date('now', 'localtime')
    """)

    if not rows:
        await update.message.reply_text("Сегодня расходов пока нет")
        return

    lines = ["Расходы за сегодня:\n"]
    for category, amount in rows:
        lines.append(f"{category.capitalize()} — {fmt_money(amount)}")

    lines.append("")
    lines.append(f"Итого: {fmt_money(total)}")
    await update.message.reply_text("\n".join(lines))


async def money_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return

    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE date(created_at, 'localtime') >= date('now', '-6 days', 'localtime')
        GROUP BY category
        ORDER BY SUM(amount) DESC
    """)
    rows = cursor.fetchall()

    total = get_sum("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE date(created_at, 'localtime') >= date('now', '-6 days', 'localtime')
    """)

    if not rows:
        await update.message.reply_text("За 7 дней расходов пока нет")
        return

    lines = ["Расходы за 7 дней:\n"]
    for category, amount in rows:
        lines.append(f"{category.capitalize()} — {fmt_money(amount)}")

    lines.append("")
    lines.append(f"Итого: {fmt_money(total)}")
    await update.message.reply_text("\n".join(lines))


async def money_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return

    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE date(created_at, 'localtime') >= date('now', 'start of month', 'localtime')
        GROUP BY category
        ORDER BY SUM(amount) DESC
    """)
    rows = cursor.fetchall()

    total = get_sum("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE date(created_at, 'localtime') >= date('now', 'start of month', 'localtime')
    """)

    if not rows:
        await update.message.reply_text("За месяц расходов пока нет")
        return

    lines = ["Расходы за месяц:\n"]
    for category, amount in rows:
        lines.append(f"{category.capitalize()} — {fmt_money(amount)}")

    lines.append("")
    lines.append(f"Итого: {fmt_money(total)}")
    await update.message.reply_text("\n".join(lines))


async def money_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return

    cursor.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        GROUP BY category
        ORDER BY SUM(amount) DESC
    """)
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Расходов по категориям пока нет")
        return

    lines = ["Категории расходов:\n"]
    for category, amount in rows:
        lines.append(f"{category.capitalize()} — {fmt_money(amount)}")

    await update.message.reply_text("\n".join(lines))


async def balance_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return

    income_total = get_sum("""
        SELECT COALESCE(SUM(amount), 0)
        FROM incomes
        WHERE date(created_at, 'localtime') = date('now', 'localtime')
    """)

    expense_total = get_sum("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE date(created_at, 'localtime') = date('now', 'localtime')
    """)

    balance = income_total - expense_total

    text = (
        "Баланс за сегодня:\n\n"
        f"Доходы: {fmt_money(income_total)}\n"
        f"Расходы: {fmt_money(expense_total)}\n"
        f"Баланс: {fmt_money(balance)}"
    )
    await update.message.reply_text(text)


async def balance_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return

    income_total = get_sum("""
        SELECT COALESCE(SUM(amount), 0)
        FROM incomes
        WHERE date(created_at, 'localtime') >= date('now', 'start of month', 'localtime')
    """)

    expense_total = get_sum("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE date(created_at, 'localtime') >= date('now', 'start of month', 'localtime')
    """)

    balance = income_total - expense_total

    text = (
        "Баланс за месяц:\n\n"
        f"Доходы: {fmt_money(income_total)}\n"
        f"Расходы: {fmt_money(expense_total)}\n"
        f"Баланс: {fmt_money(balance)}"
    )
    await update.message.reply_text(text)


async def quick_spend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if not await ensure_allowed(update):
        return

    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        return

    try:
        amount = float(parts[0].replace(",", "."))
    except Exception:
        return

    category = parts[1]
    comment = " ".join(parts[2:]) if len(parts) > 2 else ""

    cursor.execute(
        "INSERT INTO expenses(amount,category,comment,created_at) VALUES (?,?,?,?)",
        (amount, category, comment, datetime.now().isoformat())
    )
    conn.commit()

    await update.message.reply_text(
        f"💸 Расход записан\n{amount} — {category}"
    )


def register_finance(app):
    app.add_handler(CommandHandler("spend", spend))
    app.add_handler(CommandHandler("income", income))
    app.add_handler(CommandHandler("money_today", money_today))
    app.add_handler(CommandHandler("money_week", money_week))
    app.add_handler(CommandHandler("money_month", money_month))
    app.add_handler(CommandHandler("money_categories", money_categories))
    app.add_handler(CommandHandler("balance_today", balance_today))
    app.add_handler(CommandHandler("balance_month", balance_month))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, quick_spend))