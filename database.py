import sqlite3
from datetime import datetime

conn = sqlite3.connect("tasks.db", check_same_thread=False)
cursor = conn.cursor()


def init_db():
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


def log_action(task_id: int, action: str) -> None:
    cursor.execute(
        "INSERT INTO task_log (task_id, action, created_at) VALUES (?, ?, ?)",
        (task_id, action, datetime.now().isoformat())
    )
    conn.commit()