import os
from telegram.ext import ApplicationBuilder

from config import TOKEN
from database import init_db
from modules.tasks import register_tasks
from modules.finance import register_finance
from modules.reminders import register_reminders
from modules.menu import register_menu


PORT = int(os.environ.get("PORT", 8000))
BASE_URL = os.environ.get("BASE_URL")


def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    register_tasks(app)
    register_menu(app)
    register_finance(app)
    register_reminders(app)

    print("Бот запущен через webhook...")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{BASE_URL}/{TOKEN}"
    )


if __name__ == "__main__":
    main()