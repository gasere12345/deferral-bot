import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot/deferral.db")
PORT = int(os.getenv("PORT", 8080))
_ALLOWED_RAW = os.getenv("ALLOWED_IDS", "").strip()
ALLOWED_IDS = {int(x) for x in _ALLOWED_RAW.split(",") if x.strip().isdigit()}
if _ALLOWED_RAW and not ALLOWED_IDS:
    logger.warning("ALLOWED_IDS set but parsed to nothing — bot is OPEN to everyone!")
REMINDER_DAYS = int(os.getenv("REMINDER_DAYS", "3"))
TURSO_URL = os.getenv("TURSO_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
