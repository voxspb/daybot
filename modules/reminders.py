from datetime import datetime, time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import cursor, conn, log_action
from modules.tasks import USER_CHAT_IDS, format_task, get_today_counters
from modules.finance import get_sum, fmt_money


async def check_tasks(context: ContextTypes.DEFAULT_TYPE):
    if not USER_CHAT_IDS:
        return

    now = datetime.now().strftime("%H:%M")
    today_str = datetime.now().strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT id, time, text, is_daily FROM tasks WHERE time = ? ORDER BY id",
        (now,)
    )
    tasks = cursor.fetchall()

    for task_id, task_time, task_text, is_daily in tasks:
        cursor.execute("""
            SELECT COUNT(*)
            FROM task_log
            WHERE task_id = ?
              AND action = ?
              AND date(created_at, 'localtime') = ?
        """, (task_id, "reminded", today_str))
        reminded_today = cursor.fetchone()[0]

        if reminded_today > 0:
            continue

        keyboard = [
            [
                InlineKeyboardButton("✅ Сделал", callback_data=f"done:{task_id}"),
                InlineKeyboardButton("⏰ +15 мин", callback_data=f"snooze15:{task_id}"),
            ],
            [
                InlineKeyboardButton("❌ Пропустить", callback_data=f"skip:{task_id}"),
            ]
        ]

        suffix = " [daily]" if is_daily else ""

        for chat_id in USER_CHAT_IDS:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Напоминание:\n{task_time} — {task_text}{suffix}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        log_action(task_id, "reminded")


async def morning_plan(context: ContextTypes.DEFAULT_TYPE):
    if not USER_CHAT_IDS:
        return

    cursor.execute("SELECT id, time, text, is_daily FROM tasks ORDER BY time, id")
    tasks = cursor.fetchall()

    for chat_id in USER_CHAT_IDS:
        if not tasks:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Доброе утро ☀️\n\nСегодня задач пока нет."
            )
            continue

        lines = ["Доброе утро ☀️", "", "План на сегодня:", ""]
        for task in tasks:
            lines.append(format_task(task))

        await context.bot.send_message(
            chat_id=chat_id,
            text="\n".join(lines)
        )


async def evening_report(context: ContextTypes.DEFAULT_TYPE):
    if not USER_CHAT_IDS:
        return

    counters = get_today_counters()
    expense_total = get_sum("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE date(created_at, 'localtime') = date('now', 'localtime')
    """)

    income_total = get_sum("""
        SELECT COALESCE(SUM(amount), 0)
        FROM incomes
        WHERE date(created_at, 'localtime') = date('now', 'localtime')
    """)

    balance = income_total - expense_total

    total_handled = counters["done"] + counters["skip"]
    completion_rate = round((counters["done"] / total_handled) * 100) if total_handled > 0 else 0

    text = (
        "Итог дня 🌙\n\n"
        f"Напоминаний: {counters['reminded']}\n"
        f"Выполнено: {counters['done']}\n"
        f"Пропущено: {counters['skip']}\n"
        f"Отложено на 15 мин: {counters['snooze_15']}\n"
        f"Процент выполнения: {completion_rate}%\n\n"
        f"Доходы: {fmt_money(income_total)}\n"
        f"Расходы: {fmt_money(expense_total)}\n"
        f"Баланс: {fmt_money(balance)}"
    )

    for chat_id in USER_CHAT_IDS:
        await context.bot.send_message(chat_id=chat_id, text=text)


async def backup_db(context: ContextTypes.DEFAULT_TYPE):
    if not USER_CHAT_IDS:
        return

    try:
        for chat_id in USER_CHAT_IDS:
            with open("tasks.db", "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename="tasks_backup.db",
                    caption="📦 Автобэкап базы"
                )
    except Exception as e:
        print("Ошибка бэкапа:", e)


def register_reminders(app):
    job_queue = app.job_queue
    if not job_queue:
        return

    job_queue.run_repeating(check_tasks, interval=60, first=5)
    job_queue.run_daily(morning_plan, time=time(hour=9, minute=0))
    job_queue.run_daily(evening_report, time=time(hour=23, minute=0))
    job_queue.run_repeating(backup_db, interval=4 * 24 * 60 * 60, first=60)