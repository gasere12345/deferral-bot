import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import TELEGRAM_TOKEN, PORT
from bot.db import init as db_init
from bot.handlers import common, suppliers, deliveries, calendar_view
from bot.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAT_ID_ENV = "NOTIFICATION_CHAT_ID"
_scheduler = None
_health_runner = None

dp = Dispatcher()
dp.include_router(common.router)
dp.include_router(suppliers.router)
dp.include_router(deliveries.router)
dp.include_router(calendar_view.router)


async def health_check():
    global _health_runner
    from aiohttp import web
    app = web.Application()
    app.router.add_get("/health", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    _health_runner = runner
    logger.info(f"Health check server running on port {PORT}")


async def shutdown_scheduler():
    global _scheduler, _health_runner
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
    if _health_runner:
        await _health_runner.cleanup()
        logger.info("Health check server shut down")


async def main():
    global _scheduler

    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set!")
        return

    await db_init()
    logger.info("Database initialized")

    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp.shutdown.register(shutdown_scheduler)

    chat_id = os.getenv(CHAT_ID_ENV)
    if chat_id:
        try:
            _scheduler = setup_scheduler(bot, int(chat_id))
            _scheduler.start()
            logger.info(f"Daily notifications scheduled for chat {chat_id}")
        except Exception as e:
            logger.warning(f"Could not start scheduler: {e}")
    else:
        logger.info("NOTIFICATION_CHAT_ID not set — daily notifications disabled")

    try:
        asyncio.create_task(health_check())
    except Exception as e:
        logger.warning(f"Could not start health check server: {e}")

    logger.info("Bot started polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
