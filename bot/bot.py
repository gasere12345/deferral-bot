import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import TELEGRAM_TOKEN, PORT, NOTIFICATION_CHAT_IDS
from bot.db import init as db_init
from bot.handlers import common, suppliers, deliveries, calendar_view
from bot.middleware import AccessMiddleware
from bot.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_scheduler = None
_health_runner = None
_ready = False
dp = Dispatcher()
dp.update.middleware(AccessMiddleware())
dp.include_router(common.router)
dp.include_router(suppliers.router)
dp.include_router(deliveries.router)
dp.include_router(calendar_view.router)


async def _health_response(_request):
    from aiohttp import web

    if not _ready:
        return web.Response(status=503, text="STARTING")
    return web.Response(text="OK")


async def health_check():
    global _health_runner
    from aiohttp import web

    app = web.Application()
    app.router.add_get("/health", _health_response)
    app.router.add_get("/", _health_response)
    runner = web.AppRunner(app)
    try:
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
    except Exception:
        await runner.cleanup()
        logger.exception("Health check server failed to start on port %s", PORT)
        raise
    _health_runner = runner
    logger.info(f"Health check server running on port {PORT}")


async def _init_db_with_retry(attempts: int = 5, delay: float = 5.0):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            await db_init()
            return
        except Exception as e:
            last_error = e
            logger.warning(
                "Database init failed (attempt %d/%d): %s", attempt, attempts, e
            )
            if attempt < attempts:
                await asyncio.sleep(delay)
    raise RuntimeError(f"Database init failed after {attempts} attempts") from last_error


async def shutdown_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
    if _health_runner:
        await _health_runner.cleanup()
        logger.info("Health check server shut down")


async def main():
    global _scheduler, _ready

    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN not set")

    await health_check()

    await _init_db_with_retry()
    _ready = True
    logger.info("Database initialized")

    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp.shutdown.register(shutdown_scheduler)

    chat_ids = sorted(NOTIFICATION_CHAT_IDS)
    if chat_ids:
        try:
            _scheduler = setup_scheduler(bot, chat_ids)
            _scheduler.start()
            logger.info(f"Daily notifications scheduled for chats {chat_ids}")
        except Exception as e:
            logger.warning(f"Could not start scheduler: {e}")
    else:
        logger.info("NOTIFICATION_CHAT_ID not set — daily notifications disabled")

    logger.info("Bot started polling")
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
