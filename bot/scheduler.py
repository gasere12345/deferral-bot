import logging

from datetime import date
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import REMINDER_DAYS
from bot.db import get_deliveries_for_date, get_overdue, get_upcoming
from bot.reports import build_daily_text, build_weekly_text

logger = logging.getLogger(__name__)

TZ = "Europe/Minsk"


async def daily_check(bot: Bot, chat_id: int):
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    deliveries = await get_deliveries_for_date(today_str)
    overdue = await get_overdue(today_str)
    upcoming = await get_upcoming(today_str, REMINDER_DAYS)
    text = build_daily_text(deliveries, overdue, upcoming, REMINDER_DAYS, today)
    await _safe_send(bot, chat_id, text)


async def weekly_report(bot: Bot, chat_id: int):
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    week_deliveries = await get_upcoming(today_str, 6)
    today_deliveries = await get_deliveries_for_date(today_str)
    overdue = await get_overdue(today_str)
    text = build_weekly_text(today_deliveries + week_deliveries, overdue, today)
    await _safe_send(bot, chat_id, text)


async def _safe_send(bot: Bot, chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.exception("Failed to send notification: %s", e)


def setup_scheduler(bot: Bot, chat_id: int) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        daily_check,
        "cron",
        hour=9,
        minute=0,
        timezone=TZ,
        args=[bot, chat_id],
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
        args=[bot, chat_id],
        id="weekly_report",
        replace_existing=True,
    )
    return scheduler
