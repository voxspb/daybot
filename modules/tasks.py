from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import ReplyKeyboardMarkup

from database import cursor, conn, log_action
from config import ALLOWED_USERS

USER_CHAT_IDS = set()


def allowed(update: Update) -> bool:
    chat = update.effective_chat
    if not chat:
        return False
    return chat.id in ALLOWED_USERS


async def ensure_allowed(update: Update) -> bool:
    if not allowed(update):
        if update.message:
            await update.message.reply_text("Нет доступа")
        elif update.callback_query:
            await update.callback_query.answer("Нет доступа", show_alert=True)
        return False
    return True


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

    for action_name, count in rows:
        counters[action_name] = count

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return

    USER_CHAT_IDS.add(update.effective_chat.id)

    keyboard = [
        ["🍽 Питание", "💸 Финансы"],
        ["📅 День", "👶 Ася"],
        ["📊 Аналитика"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    text = (
        "Бот режима дня запущен.\n\n"
        "Открыл главное меню 👇"
    )

    await update.message.reply_text(
        text,
        reply_markup=reply_markup
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_allowed(update):
        return

    USER_CHAT_IDS.add(update.effective_chat.id)

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
    if not await ensure_allowed(update):
        return

    USER_CHAT_IDS.add(update.effective_chat.id)

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
    if not await ensure_allowed(update):
        return

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
    if not await ensure_allowed(update):
        return

    counters = get_today_counters()
    total_handled = counters["done"] + counters["skip"]
    completion_rate = round((counters["done"] / total_handled) * 100) if total_handled > 0 else 0

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
    if not await ensure_allowed(update):
        return

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
    if not await ensure_allowed(update):
        return

    daily_tasks = get_daily_tasks()

    if not daily_tasks:
        await update.message.reply_text("Daily-привычек пока нет")
        return

    lines = ["Серии привычек 🔥", ""]

    for task_id, task_time, task_text, is_daily in daily_tasks:
        streak = get_task_streak(task_id)
        lines.append(f"{task_text} — {streak} дней подряд")

    await update.message.reply_text("\n".join(lines))


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    if not await ensure_allowed(update):
        return

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


def register_tasks(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("delete", delete))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("weekly", weekly))
    app.add_handler(CommandHandler("streaks", streaks))
    app.add_handler(CallbackQueryHandler(button))