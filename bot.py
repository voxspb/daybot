import os
import sqlite3
from datetime import datetime, timedelta, time

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
TOKEN = os.getenv("DAYBOT_TOKEN", "")
ALLOWED_USERS = {
    805101340,
    987654321
}
if not TOKEN:
    raise RuntimeError("Не задан DAYBOT_TOKEN")

conn = sqlite3.connect("tasks.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    text TEXT NOT NULL,
    is_daily INTEGER NOT NULL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS task_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    action TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    comment TEXT DEFAULT '',
    created_at TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS incomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    source TEXT NOT NULL,
    comment TEXT DEFAULT '',
    created_at TEXT NOT NULL
)
""")
conn.commit()

cursor.execute("PRAGMA table_info(tasks)")
columns = [row[1] for row in cursor.fetchall()]
if "is_daily" not in columns:
    cursor.execute("ALTER TABLE tasks ADD COLUMN is_daily INTEGER NOT NULL DEFAULT 0")
    conn.commit()

ALLOWED_USERS = set()


def log_action(task_id: int, action: str) -> None:
    cursor.execute(
        "INSERT INTO task_log (task_id, action, created_at) VALUES (?, ?, ?)",
        (task_id, action, datetime.now().isoformat())
    )
    conn.commit()


def get_task(task_id: int):
    cursor.execute(
        "SELECT id, time, text, is_daily FROM tasks WHERE id = ?",
        (task_id,)
    )
    return cursor.fetchone()


def get_daily_tasks():
    cursor.execute(
        "SELECT id, time, text, is_daily FROM tasks WHERE is_daily = 1 ORDER BY time, id"
    )
    return cursor.fetchall()


def format_task(task_row) -> str:
    task_id, task_time, task_text, is_daily = task_row
    suffix = " [daily]" if is_daily else ""
    return f"{task_id}. {task_time} — {task_text}{suffix}"


def parse_time_str(time_str: str) -> datetime:
    return datetime.strptime(time_str, "%H:%M")


def shift_time_str(time_str: str, minutes: int) -> str:
    dt = parse_time_str(time_str)
    shifted = dt + timedelta(minutes=minutes)
    return shifted.strftime("%H:%M")


def get_today_counters():
    cursor.execute("""
        SELECT action, COUNT(*)
        FROM task_log
        WHERE date(created_at, 'localtime') = date('now', 'localtime')
        GROUP BY action
    """)
    rows = cursor.fetchall()

    counters = {
        "reminded": 0,
        "done": 0,
        "skip": 0,
        "snooze_15": 0,
        "deleted": 0,
    }

    for action, count in rows:
        counters[action] = count

    return counters


def did_task_action_on_date(task_id: int, action: str, date_str: str) -> bool:
    cursor.execute("""
        SELECT COUNT(*)
        FROM task_log
        WHERE task_id = ?
          AND action = ?
          AND date(created_at, 'localtime') = ?
    """, (task_id, action, date_str))
    return cursor.fetchone()[0] > 0


def get_task_streak(task_id: int) -> int:
    streak = 0
    today = datetime.now().date()

    for days_back in range(0, 365):
        check_date = today - timedelta(days=days_back)
        check_date_str = check_date.strftime("%Y-%m-%d")

        if did_task_action_on_date(task_id, "done", check_date_str):
            streak += 1
        else:
            break

    return streak


def get_weekly_done_count(task_id: int) -> int:
    today = datetime.now().date()
    count = 0

    for days_back in range(0, 7):
        check_date = today - timedelta(days=days_back)
        check_date_str = check_date.strftime("%Y-%m-%d")
        if did_task_action_on_date(task_id, "done", check_date_str):
            count += 1

    return count


def fmt_money(value: float) -> str:
    return f"{value:.2f}"


def get_sum(query: str, params=()):
    cursor.execute(query, params)
    value = cursor.fetchone()[0]
    return float(value or 0)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global USER_CHAT_ID
    ALLOWED_USERS.add(update.effective_chat.id)

    text = (
        "Бот режима дня запущен.\n\n"
        "Задачи:\n"
        "/add HH:MM задача\n"
        "/add HH:MM задача daily\n"
        "/today\n"
        "/stats\n"
        "/weekly\n"
        "/streaks\n"
        "/delete ID\n\n"
        "Финансы:\n"
        "/spend сумма категория\n"
        "/income сумма источник\n"
        "/money_today\n"
        "/money_week\n"
        "/money_month\n"
        "/money_categories\n"
        "/balance_today\n"
        "/balance_month\n\n"
        "Примеры:\n"
        "/add 10:00 зарядка\n"
        "/add 22:30 чтение daily\n"
        "/spend 500 продукты\n"
        "/income 2500 подработка"
    )
    await update.message.reply_text(text)


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global USER_CHAT_ID
    USER_CHAT_ID = update.effective_chat.id

    try:
        if len(context.args) < 2:
            raise ValueError("not enough args")

        task_time = context.args[0]
        raw_args = context.args[1:]

        datetime.strptime(task_time, "%H:%M")

        is_daily = 0
        if raw_args[-1].lower() == "daily":
            is_daily = 1
            raw_args = raw_args[:-1]

        task_text = " ".join(raw_args).strip()

        if not task_text:
            raise ValueError("empty task text")

        cursor.execute(
            "INSERT INTO tasks (time, text, is_daily) VALUES (?, ?, ?)",
            (task_time, task_text, is_daily)
        )
        conn.commit()

        task_id = cursor.lastrowid
        suffix = " [daily]" if is_daily else ""
        await update.message.reply_text(
            f"Добавлено:\n{task_id}. {task_time} — {task_text}{suffix}"
        )

    except Exception:
        await update.message.reply_text(
            "Формат:\n"
            "/add 10:00 зарядка\n"
            "/add 22:30 чтение daily"
        )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global USER_CHAT_ID
    USER_CHAT_ID = update.effective_chat.id

    cursor.execute("SELECT id, time, text, is_daily FROM tasks ORDER BY time, id")
    tasks = cursor.fetchall()

    if not tasks:
        await update.message.reply_text("Задач пока нет")
        return

    lines = ["Сегодня:\n"]
    for task in tasks:
        lines.append(format_task(task))

    await update.message.reply_text("\n".join(lines))


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_id = int(context.args[0])
    except Exception:
        await update.message.reply_text("Формат: /delete ID")
        return

    task = get_task(task_id)
    if not task:
        await update.message.reply_text("Задача с таким ID не найдена")
        return

    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()

    log_action(task_id, "deleted")
    await update.message.reply_text(f"Удалено:\n{format_task(task)}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    counters = get_today_counters()

    total_handled = counters["done"] + counters["skip"]
    completion_rate = 0
    if total_handled > 0:
        completion_rate = round((counters["done"] / total_handled) * 100)

    text = (
        "Статистика за сегодня:\n\n"
        f"Напоминаний: {counters['reminded']}\n"
        f"Выполнено: {counters['done']}\n"
        f"Пропущено: {counters['skip']}\n"
        f"Отложено на 15 мин: {counters['snooze_15']}\n"
        f"Удалено: {counters['deleted']}\n"
        f"Процент выполнения: {completion_rate}%"
    )
    await update.message.reply_text(text)


async def weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    daily_tasks = get_daily_tasks()

    if not daily_tasks:
        await update.message.reply_text("Daily-привычек пока нет")
        return

    lines = ["Отчёт за 7 дней 📊", ""]
    percentages = []

    for task_id, task_time, task_text, is_daily in daily_tasks:
        done_count = get_weekly_done_count(task_id)
        percent = round((done_count / 7) * 100)
        percentages.append(percent)
        lines.append(f"{task_text} — {done_count}/7")

    avg_percent = round(sum(percentages) / len(percentages)) if percentages else 0
    lines.append("")
    lines.append(f"Средний процент выполнения: {avg_percent}%")

    await update.message.reply_text("\n".join(lines))


async def streaks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    daily_tasks = get_daily_tasks()

    if not daily_tasks:
        await update.message.reply_text("Daily-привычек пока нет")
        return

    lines = ["Серии привычек 🔥", ""]

    for task_id, task_time, task_text, is_daily in daily_tasks:
        streak = get_task_streak(task_id)
        lines.append(f"{task_text} — {streak} дней подряд")

    await update.message.reply_text("\n".join(lines))


async def spend(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def check_tasks(context: ContextTypes.DEFAULT_TYPE):
    global USER_CHAT_ID

    if not USER_CHAT_ID:
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

        await context.bot.send_message(
            chat_id=USER_CHAT_ID,
            text=f"Напоминание:\n{task_time} — {task_text}{suffix}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        log_action(task_id, "reminded")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    try:
        action, task_id_raw = data.split(":")
        task_id = int(task_id_raw)
    except Exception:
        await query.edit_message_text("Ошибка обработки кнопки")
        return

    task = get_task(task_id)

    if action == "done":
        if not task:
            await query.edit_message_text("Задача уже удалена или не найдена")
            return

        log_action(task_id, "done")
        await query.edit_message_text(f"Отмечено как выполнено ✅\n{format_task(task)}")
        return

    if action == "skip":
        if not task:
            await query.edit_message_text("Задача уже удалена или не найдена")
            return

        log_action(task_id, "skip")
        await query.edit_message_text(f"Отмечено как пропущено ❌\n{format_task(task)}")
        return

    if action == "snooze15":
        if not task:
            await query.edit_message_text("Задача уже удалена или не найдена")
            return

        task_id_db, old_time, task_text, is_daily = task
        new_time = shift_time_str(old_time, 15)

        cursor.execute(
            "UPDATE tasks SET time = ? WHERE id = ?",
            (new_time, task_id)
        )
        conn.commit()

        log_action(task_id, "snooze_15")
        suffix = " [daily]" if is_daily else ""
        await query.edit_message_text(
            f"Перенесено на 15 минут ⏰\n{task_id_db}. {new_time} — {task_text}{suffix}"
        )
        return

    await query.edit_message_text("Неизвестное действие")


async def morning_plan(context: ContextTypes.DEFAULT_TYPE):
    global USER_CHAT_ID

    if not USER_CHAT_ID:
        return

    cursor.execute("SELECT id, time, text, is_daily FROM tasks ORDER BY time, id")
    tasks = cursor.fetchall()

    if not tasks:
        await context.bot.send_message(
            chat_id=USER_CHAT_ID,
            text="Доброе утро ☀️\n\nСегодня задач пока нет."
        )
        return

    lines = ["Доброе утро ☀️", "", "План на сегодня:", ""]
    for task in tasks:
        lines.append(format_task(task))

    await context.bot.send_message(
        chat_id=USER_CHAT_ID,
        text="\n".join(lines)
    )


async def evening_report(context: ContextTypes.DEFAULT_TYPE):
    global USER_CHAT_ID

    if not USER_CHAT_ID:
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
    completion_rate = 0
    if total_handled > 0:
        completion_rate = round((counters["done"] / total_handled) * 100)

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

    await context.bot.send_message(
        chat_id=USER_CHAT_ID,
        text=text
    )
async def backup_db(context: ContextTypes.DEFAULT_TYPE):
    global USER_CHAT_ID

    if not USER_CHAT_ID:
        return

    try:
        with open("tasks.db", "rb") as f:
            await context.bot.send_document(
                chat_id=USER_CHAT_ID,
                document=f,
                filename="tasks_backup.db",
                caption="📦 Автобэкап базы"
            )
    except Exception as e:
        print("Ошибка бэкапа:", e)
async def quick_spend(update, context):

    if not update.message:
        return

    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        return

    try:
        amount = float(parts[0].replace(",", "."))
    except:
        return

    category = parts[1]

    comment = ""
    if len(parts) > 2:
        comment = " ".join(parts[2:])

    cursor.execute(
        "INSERT INTO expenses(amount,category,comment,created_at) VALUES (?,?,?,?)",
        (amount, category, comment, datetime.now().isoformat())
    )

    conn.commit()

    await update.message.reply_text(
        f"💸 Расход записан\n{amount} — {category}"
    )
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ALLOWED_USERS:
        await update.message.reply_text("Нет доступа")
        return False
    return True
    app.add_handler(CommandHandler("start", start))
    ...
    app.add_handler(CallbackQueryHandler(button))

    job_queue = app.job_queue
    job_queue.run_repeating(check_tasks, interval=60, first=5)
    job_queue.run_daily(morning_plan, time=time(hour=9, minute=0))
    job_queue.run_daily(evening_report, time=time(hour=23, minute=0))
    job_queue.run_repeating(
    backup_db,
    interval=4 * 24 * 60 * 60,
    first=60
)

    print("Бот запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
async def quick_spend(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    text = update.message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        return

    try:
        amount = float(parts[0].replace(",", "."))
    except:
        return

    category = parts[1]

    comment = ""
    if len(parts) > 2:
        comment = " ".join(parts[2:])

    cursor.execute(
        "INSERT INTO expenses(amount,category,comment,created_at) VALUES (?,?,?,?)",
        (amount, category, comment, datetime.now().isoformat())
    )

    conn.commit()

    await update.message.reply_text(
        f"💸 Расход записан\n{amount} — {category}"
    )
