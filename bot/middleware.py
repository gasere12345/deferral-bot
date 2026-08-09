import logging

from aiogram import BaseMiddleware

from bot.config import ALLOWED_IDS

logger = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data: dict):
        if not ALLOWED_IDS:
            return await handler(event, data)
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        user_id = user.id if user else None
        chat_id = chat.id if chat else None
        if user_id in ALLOWED_IDS or chat_id in ALLOWED_IDS:
            return await handler(event, data)
        logger.info("Blocked access from user=%s chat=%s", user_id, chat_id)
        return
