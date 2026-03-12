from telegram.ext import ApplicationBuilder

from config import TOKEN
from database import init_db
from modules.tasks import register_tasks
from modules.finance import register_finance
from modules.reminders import register_reminders


def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    register_tasks(app)
    register_finance(app)
    register_reminders(app)

    print("Бот запущен...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=[]
    )


if __name__ == "__main__":
    main()