import os

TOKEN = os.getenv("DAYBOT_TOKEN", "")

ALLOWED_USERS = {
    805101340,
    987654321,
}

if not TOKEN:
    raise RuntimeError("Не задан DAYBOT_TOKEN")