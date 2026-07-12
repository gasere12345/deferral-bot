import calendar
from datetime import datetime, date
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.db import get_deliveries_for_date, get_delivery, mark_paid
from bot.calendar_utils import calc_deferral_end, is_working_day, month_range

router = Router()


def _month_name(year: int, month: int) -> str:
    names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    return names[month]


def _build_calendar(year: int, month: int, highlight_dates: set = None):
    if highlight_dates is None:
        highlight_dates = set()
    cal = calendar.monthcalendar(year, month)
    names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

    kb = []
    kb.append([InlineKeyboardButton(text=f"{names[month]} {year}", callback_data="cal:ignore")])
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.append([InlineKeyboardButton(text=d, callback_data="cal:ignore") for d in weekdays])

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="cal:ignore"))
            else:
                d = date(year, month, day)
                label = str(day)
                key = d.strftime("%Y-%m-%d")
                if key in highlight_dates:
                    label = f"💰{day}"
                elif not is_working_day(d):
                    label = f"•{day}"
                row.append(InlineKeyboardButton(
                    text=label,
                    callback_data=f"cal:day:{year}:{month}:{day}",
                ))
        kb.append(row)

    prev = month - 1
    prev_y = year
    if prev == 0:
        prev = 12
        prev_y -= 1
    next_m = month + 1
    next_y = year
    if next_m == 13:
        next_m = 1
        next_y += 1
    kb.append([
        InlineKeyboardButton(text="◀", callback_data=f"cal:nav:{prev_y}:{prev}"),
        InlineKeyboardButton(text="Сегодня", callback_data="cal:today"),
        InlineKeyboardButton(text="▶", callback_data=f"cal:nav:{next_y}:{next_m}"),
    ])
    kb.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == "menu:calendar")
async def show_calendar(callback: CallbackQuery):
    today = date.today()
    await _render_calendar(callback.message, today.year, today.month, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("cal:nav:"))
async def navigate_calendar(callback: CallbackQuery):
    _, _, year, month = callback.data.split(":")
    await _render_calendar(callback.message, int(year), int(month), edit=True)
    await callback.answer()


@router.callback_query(F.data == "cal:today")
async def calendar_today(callback: CallbackQuery):
    today = date.today()
    await _render_calendar(callback.message, today.year, today.month, edit=True)
    await callback.answer()


@router.callback_query(F.data == "cal:ignore")
async def cal_ignore(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("cal:day:"))
async def show_day_deliveries(callback: CallbackQuery):
    _, _, year, month, day = callback.data.split(":")
    target = f"{year}-{int(month):02d}-{int(day):02d}"
    deliveries = await get_deliveries_for_date(target)

    d = date(int(year), int(month), int(day))
    weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][d.weekday()]
    header = f"📅 {d.day} {_month_name(d.year, d.month)} {d.year} ({weekday})"

    if not deliveries:
        text = f"{header}\n\nНет платежей на этот день."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 К календарю", callback_data=f"cal:nav:{year}:{month}")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")],
        ])
    else:
        lines = [header, ""]
        total = 0
        for dv in deliveries:
            paid = "✅" if dv["paid"] else "⏳"
            total += dv["amount"] or 0
            lines.append(f"{paid} <b>{dv['supplier_name']}</b> — {dv['amount']:,.0f} руб.")
        lines.append(f"\n💰 Итого: {total:,.0f} руб.")
        text = "\n".join(lines)

        buttons = []
        for dv in deliveries:
            if not dv["paid"]:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"✅ Оплатить #{dv['id']} — {dv['supplier_name']}",
                        callback_data=f"cal:pay:{dv['id']}:{year}:{month}",
                    )
                ])
        buttons.append([InlineKeyboardButton(
            text="📅 К календарю",
            callback_data=f"cal:nav:{year}:{month}",
        )])
        buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("cal:pay:"))
async def pay_from_calendar(callback: CallbackQuery):
    parts = callback.data.split(":")
    delivery_id = int(parts[2])
    year = parts[3]
    month = parts[4]
    await mark_paid(delivery_id)
    dv = await get_delivery(delivery_id)
    await callback.answer(f"✅ Поставка #{delivery_id} оплачена!", show_alert=True)
    await _render_calendar(callback.message, int(year), int(month), edit=True)


async def _render_calendar(message: types.Message, year: int, month: int, edit: bool = False):
    highlight = set()
    for d in await _get_all_deferral_dates():
        if d.startswith(f"{year}-{month:02d}"):
            highlight.add(d)

    kb = _build_calendar(year, month, highlight)
    names = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    header = f"📅 <b>{names[month]} {year}</b>\n💰 — есть платеж  • — выходной/праздник"

    if edit:
        await message.edit_text(header, reply_markup=kb)
    else:
        await message.answer(header, reply_markup=kb)


async def _get_all_deferral_dates() -> set:
    from bot.db import get_deliveries
    all_deliveries = await get_deliveries(unpaid_only=True)
    dates = set()
    for d in all_deliveries:
        end = calc_deferral_end(d["delivery_date"], d["deferral_days"], d["manual_end_date"])
        dates.add(end)
    return dates
