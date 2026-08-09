import calendar
from datetime import date
from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.db import get_deliveries_for_date, get_unpaid_with_deferral_end, get_overdue, get_delivery, mark_paid
from bot.calendar_utils import is_working_day, month_name, MONTH_NAMES
from bot.reports import build_overdue_text

router = Router()


def _build_calendar(year: int, month: int, highlight_dates: set = None, overdue_dates: set = None):
    if highlight_dates is None:
        highlight_dates = set()
    if overdue_dates is None:
        overdue_dates = set()
    cal = calendar.monthcalendar(year, month)

    kb = []
    kb.append([InlineKeyboardButton(text=f"{MONTH_NAMES[month]} {year}", callback_data="cal:ignore")])
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
                if key in overdue_dates:
                    label = f"🔴{day}"
                elif key in highlight_dates:
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
        InlineKeyboardButton(text="▶", callback_data=f"cal:nav:{next_y}:{next_m}"),
    ])
    kb.append([
        InlineKeyboardButton(text="⚠️ Просрочено", callback_data="menu:overdue"),
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main"),
    ])
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


@router.callback_query(lambda c: c.data == "cal:today")
async def calendar_today(callback: CallbackQuery):
    today = date.today()
    await _render_calendar(callback.message, today.year, today.month, edit=True)
    await callback.answer()


@router.callback_query(F.data == "menu:overdue")
async def show_overdue(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await render_overdue_view(callback.message)
    await callback.answer()


async def render_overdue_view(message: types.Message):
    today = date.today()
    overdue = await get_overdue(today.strftime("%Y-%m-%d"))
    text = build_overdue_text(overdue, today)
    buttons = []
    for ov in overdue:
        buttons.append([
            InlineKeyboardButton(
                text=f"✅ Оплатить #{ov['id']} — {ov['supplier_name']}",
                callback_data=f"delivery:pay:{ov['id']}:overdue",
            )
        ])
    buttons.append([InlineKeyboardButton(text="📅 Календарь", callback_data="menu:calendar")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.edit_text(text, reply_markup=kb)


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
    header = f"📅 {d.day} {month_name(d.month)} {d.year} ({weekday})"

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
    today_str = date.today().strftime("%Y-%m-%d")
    unpaid = await get_unpaid_with_deferral_end()
    highlight = set()
    overdue = set()
    prefix = f"{year}-{month:02d}"
    for d in unpaid:
        end = d["deferral_end"]
        if end.startswith(prefix):
            if end < today_str:
                overdue.add(end)
            else:
                highlight.add(end)

    kb = _build_calendar(year, month, highlight, overdue)
    header = (
        f"📅 <b>{MONTH_NAMES[month]} {year}</b>\n"
        f"💰 — есть платеж  🔴 — просрочено  • — выходной/праздник"
    )

    if edit:
        try:
            await message.edit_text(header, reply_markup=kb)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
    else:
        await message.answer(header, reply_markup=kb)
