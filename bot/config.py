import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot/deferral.db")
PORT = int(os.getenv("PORT", 8080))
ALLOWED_IDS = {int(x) for x in os.getenv("ALLOWED_IDS", "").split(",") if x.strip().isdigit()}
REMINDER_DAYS = int(os.getenv("REMINDER_DAYS", "3"))
