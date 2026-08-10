import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import REMINDER_DAYS
from bot.calendar_utils import today_minsk
from bot.db import get_deliveries_for_date, get_overdue, get_upcoming
from bot.reports import build_daily_text, build_weekly_text

logger = logging.getLogger(__name__)

TZ = "Europe/Minsk"


async def daily_check(bot: Bot, chat_ids):
    today = today_minsk()
    today_str = today.strftime("%Y-%m-%d")
    deliveries = await get_deliveries_for_date(today_str)
    overdue = await get_overdue(today_str)
    upcoming = await get_upcoming(today_str, REMINDER_DAYS)
    text = build_daily_text(deliveries, overdue, upcoming, REMINDER_DAYS, today)
    await _safe_send(bot, chat_ids, text)


async def weekly_report(bot: Bot, chat_ids):
    today = today_minsk()
    today_str = today.strftime("%Y-%m-%d")
    week_deliveries = await get_upcoming(today_str, 6)
    today_deliveries = await get_deliveries_for_date(today_str)
    overdue = await get_overdue(today_str)
    text = build_weekly_text(today_deliveries + week_deliveries, overdue, today)
    await _safe_send(bot, chat_ids, text)


async def _safe_send(bot: Bot, chat_ids, text: str):
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, text)
        except Exception as e:
            logger.exception("Failed to send notification to %s: %s", chat_id, e)


def setup_scheduler(bot: Bot, chat_ids) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        daily_check,
        "cron",
        hour=9,
        minute=0,
        timezone=TZ,
        args=[bot, chat_ids],
        id="daily_payment_check",
        replace_existing=True,
    )
    scheduler.add_job(
        weekly_report,
        "cron",
        day_of_week="mon",
        hour=9,
        minute=10,
        timezone=TZ,
        args=[bot, chat_ids],
        id="weekly_report",
        replace_existing=True,
    )
    return scheduler
