import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot/deferral.db")
PORT = int(os.getenv("PORT", 8080))
