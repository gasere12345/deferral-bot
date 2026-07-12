import logging

from datetime import date
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.db import get_deliveries_for_date
from bot.calendar_utils import month_name

logger = logging.getLogger(__name__)


async def daily_check(bot: Bot, chat_id: int):
    today = date.today().strftime("%Y-%m-%d")
    deliveries = await get_deliveries_for_date(today)
    d = date.today()
    weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][d.weekday()]

    if not deliveries:
        text = (
            f"☀️ <b>Доброе утро!</b>\n"
            f"На сегодня ({d.day} {month_name(d.month)}, {weekday}) "
            f"платежей нет. Спокойный день!"
        )
    else:
        lines = [
            f"☀️ <b>Доброе утро! Сегодня нужно оплатить:</b> ({d.day} {month_name(d.month)} {d.year}, {weekday})",
            "",
        ]
        total = 0
        for dv in deliveries:
            total += dv["amount"] or 0
            lines.append(
                f"💰 <b>{dv['supplier_name']}</b> — {dv['amount']:,.0f} руб.\n"
            )
        lines.append(f"💳 Итого: <b>{total:,.0f} руб.</b>")
        text = "\n".join(lines)

    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.exception("Failed to send daily notification: %s", e)


def setup_scheduler(bot: Bot, chat_id: int) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        daily_check,
        "cron",
        hour=8,
        minute=0,
        args=[bot, chat_id],
        id="daily_payment_check",
        replace_existing=True,
    )
    return scheduler
