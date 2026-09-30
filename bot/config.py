import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("%s=%r is not an integer — falling back to %d", name, raw, default)
        return default


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot/deferral.db")
PORT = _int_env("PORT", 8080)
_ALLOWED_RAW = os.getenv("ALLOWED_IDS", "").strip()
ALLOWED_IDS = {int(x) for x in _ALLOWED_RAW.split(",") if x.strip().isdigit()}
if _ALLOWED_RAW and not ALLOWED_IDS:
    logger.warning("ALLOWED_IDS set but parsed to nothing — bot is OPEN to everyone!")
REMINDER_DAYS = _int_env("REMINDER_DAYS", 3)
NOTIFICATION_CHAT_IDS = {int(x) for x in os.getenv("NOTIFICATION_CHAT_ID", "").split(",") if x.strip().isdigit()}
TURSO_URL = os.getenv("TURSO_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
