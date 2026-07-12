import calendar
from datetime import date, datetime

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.db import (
    add_delivery, get_deliveries, get_delivery,
    mark_paid, edit_delivery, delete_delivery,
    get_all_suppliers, get_supplier,
    get_deliveries_for_date, set_manual_end_date,
)
from bot.calendar_utils import calc_deferral_end, month_name

router = Router()


class AddDelivery(StatesGroup):
    supplier = State()
    date = State()
    amount = State()


def _date_picker_kb(year: int, month: int):
    cal = calendar.monthcalendar(year, month)
    kb = []
    kb.append([InlineKeyboardButton(text=f"{month_name(month)} {year}", callback_data="dp:ignore")])
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.append([InlineKeyboardButton(text=d, callback_data="dp:ignore") for d in weekdays])
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="dp:ignore"))
            else:
                row.append(InlineKeyboardButton(
                    text=str(day),
                    callback_data=f"dp:day:{year}:{month}:{day}",
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
        InlineKeyboardButton(text="◀", callback_data=f"dp:nav:{prev_y}:{prev}"),
        InlineKeyboardButton(text="Сегодня", callback_data="dp:today"),
        InlineKeyboardButton(text="▶", callback_data=f"dp:nav:{next_y}:{next_m}"),
    ])
    kb.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="menu:deliveries")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == "menu:deliveries")
async def deliveries_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить поставку", callback_data="delivery:add:0")],
        [InlineKeyboardButton(text="📋 Поставки по поставщику", callback_data="delivery:list:0")],
        [InlineKeyboardButton(text="💰 Сегодня к оплате", callback_data="menu:today")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")],
    ])
    await callback.message.edit_text("📦 <b>Поставки</b>\nВыбери действие:", reply_markup=kb)
    await callback.answer()


async def _show_today_payments(callback: CallbackQuery):
    today = date.today().strftime("%Y-%m-%d")
    deliveries = await get_deliveries_for_date(today)
    d = date.today()
    weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][d.weekday()]
    header = f"💰 <b>Сегодня к оплате</b> — {d.day} {month_name(d.month)} {d.year} ({weekday})"
    if not deliveries:
        text = f"{header}\n\n🎉 На сегодня платежей нет."
    else:
        lines = [header, ""]
        total = 0
        for dv in deliveries:
            total += dv["amount"] or 0
            lines.append(
                f"• <b>{dv['supplier_name']}</b> — {dv['amount']:,.0f} руб.\n"
                f"  (поставка {dv['delivery_date']})"
            )
        lines.append(f"\n💰 Итого к оплате: {total:,.0f} руб.")
        text = "\n".join(lines)

    buttons = []
    for dv in deliveries:
        if not dv["paid"]:
            buttons.append([
                InlineKeyboardButton(
                    text=f"✅ Оплатить #{dv['id']} — {dv['supplier_name']}",
                    callback_data=f"delivery:pay:{dv['id']}:today",
                )
            ])
    buttons.append([InlineKeyboardButton(text="📅 Календарь", callback_data="menu:calendar")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "menu:today")
async def today_payments(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_today_payments(callback)
    await callback.answer()


# ─── ADD DELIVERY FLOW ───────────────────────────────────

@router.callback_query(F.data.startswith("delivery:add:"))
async def add_delivery_start(callback: CallbackQuery, state: FSMContext):
    supplier_id = int(callback.data.split(":")[2])
    if supplier_id == 0:
        suppliers = await get_all_suppliers()
        if not suppliers:
            await callback.answer("Сначала добавьте поставщика!", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=s["name"], callback_data=f"delivery:add:{s['id']}")]
            for s in suppliers
        ] + [
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="menu:deliveries")],
        ])
        await callback.message.edit_text("Выберите поставщика:", reply_markup=kb)
        await callback.answer()
    else:
        await state.update_data(supplier_id=supplier_id)
        await state.set_state(AddDelivery.date)
        today = date.today()
        await callback.message.edit_text(
            "📅 Выберите <b>дату поставки</b>:",
            reply_markup=_date_picker_kb(today.year, today.month),
        )
        await callback.answer()


@router.callback_query(AddDelivery.date, F.data.startswith("dp:nav:"))
async def date_picker_nav(callback: CallbackQuery, state: FSMContext):
    _, _, year, month = callback.data.split(":")
    await callback.message.edit_reply_markup(
        reply_markup=_date_picker_kb(int(year), int(month)),
    )
    await callback.answer()


@router.callback_query(AddDelivery.date, F.data == "dp:today")
async def date_picker_today(callback: CallbackQuery, state: FSMContext):
    today = date.today()
    await callback.message.edit_reply_markup(
        reply_markup=_date_picker_kb(today.year, today.month),
    )
    await callback.answer()


@router.callback_query(AddDelivery.date, F.data.startswith("dp:day:"))
async def date_picker_day(callback: CallbackQuery, state: FSMContext):
    _, _, year, month, day = callback.data.split(":")
    selected = f"{year}-{int(month):02d}-{int(day):02d}"
    await state.update_data(delivery_date=selected)
    await state.set_state(AddDelivery.amount)
    d = date(int(year), int(month), int(day))
    await callback.message.edit_text(
        f"📅 Дата поставки: <b>{d.day} {month_name(d.month)} {d.year}</b>\n\n"
        f"💰 Введите <b>сумму поставки</b> (в рублях):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="menu:deliveries")],
        ]),
    )
    await callback.answer()


@router.message(AddDelivery.amount)
async def add_delivery_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительное число (сумма в рублях):")
        return
    data = await state.get_data()
    supplier_id = data["supplier_id"]
    delivery_date = data["delivery_date"]
    try:
        delivery_id = await add_delivery(supplier_id, delivery_date, amount)
    except Exception:
        await message.answer("❌ Ошибка: поставщик больше не существует.")
        await state.clear()
        return
    await state.clear()

    s = await get_supplier(supplier_id)
    deferral_end = calc_deferral_end(delivery_date, s["deferral_days"])
    d = datetime.strptime(delivery_date, "%Y-%m-%d").date()
    text = (
        f"✅ <b>Поставка добавлена!</b>\n\n"
        f"Поставщик: {s['name']}\n"
        f"Дата поставки: {d.day} {month_name(d.month)} {d.year}\n"
        f"Сумма: {amount:,.0f} руб.\n"
        f"⏳ Последний день оплаты: <b>{deferral_end}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 К поставкам", callback_data=f"delivery:list:{supplier_id}")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "dp:ignore")
async def dp_ignore(callback: CallbackQuery):
    await callback.answer()


# ─── LIST / PAY ──────────────────────────────────────────

async def _show_list(message: types.Message, supplier_id: int):
    s = await get_supplier(supplier_id)
    deliveries = await get_deliveries(supplier_id=supplier_id)
    if not deliveries:
        text = f"📦 У <b>{s['name']}</b> пока нет поставок."
    else:
        lines = [f"📦 <b>{s['name']}</b> — поставки:"]
        for dv in deliveries:
            paid = "✅" if dv["paid"] else "⏳"
            end = calc_deferral_end(dv["delivery_date"], dv["deferral_days"], dv["manual_end_date"])
            lines.append(
                f"\n{paid} <b>#{dv['id']}</b> от {dv['delivery_date']}\n"
                f"   Сумма: {dv['amount']:,.0f} руб.\n"
                f"   Оплатить до: {end}"
            )
        text = "".join(lines)

    buttons = []
    for dv in deliveries:
        if not dv["paid"]:
            buttons.append([
                InlineKeyboardButton(
                    text=f"✅ Оплатить #{dv['id']}",
                    callback_data=f"delivery:pay:{dv['id']}:list:{supplier_id}",
                )
            ])
    buttons.append([InlineKeyboardButton(text="➕ Добавить", callback_data=f"delivery:add:{supplier_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 К поставщику", callback_data=f"supplier:view:{supplier_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("delivery:list:"))
async def list_deliveries(callback: CallbackQuery):
    supplier_id = int(callback.data.split(":")[2])
    if supplier_id == 0:
        suppliers = await get_all_suppliers()
        if not suppliers:
            await callback.answer("Нет поставщиков!", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=s["name"], callback_data=f"delivery:list:{s['id']}")]
            for s in suppliers
        ] + [
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="menu:deliveries")],
        ])
        await callback.message.edit_text("Выберите поставщика:", reply_markup=kb)
        await callback.answer()
        return

    await _show_list(callback.message, supplier_id)
    await callback.answer()


@router.callback_query(F.data.startswith("delivery:pay:"))
async def pay_delivery_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    delivery_id = int(parts[2])
    context = parts[3]
    await mark_paid(delivery_id)
    await callback.answer(f"✅ Поставка #{delivery_id} отмечена оплаченной!", show_alert=True)

    if context == "today":
        await _show_today_payments(callback)
    elif context == "list":
        supplier_id = int(parts[4])
        await _show_list(callback.message, supplier_id)
    elif context == "reschedule":
        supplier_id = int(parts[4])
        await _show_reschedule_list(callback.message, supplier_id)
    else:
        await callback.message.edit_text("✅ Готово!")


# ─── MANUAL RESCHEDULE ───────────────────────────────────

class RescheduleDelivery(StatesGroup):
    picking = State()
    date = State()


async def _show_reschedule_list(message: types.Message, supplier_id: int):
    s = await get_supplier(supplier_id)
    deliveries = await get_deliveries(supplier_id=supplier_id, unpaid_only=True)
    if not deliveries:
        await message.edit_text(
            f"У <b>{s['name']}</b> нет неоплаченных поставок для переноса.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"supplier:view:{supplier_id}")],
            ]),
        )
        return
    lines = [f"📅 <b>Перенос даты оплаты</b> — {s['name']}", "Выбери поставку:"]
    buttons = []
    for dv in deliveries:
        end = calc_deferral_end(dv["delivery_date"], dv["deferral_days"], dv.get("manual_end_date"))
        label = f"#{dv['id']} — {dv['amount']:,.0f} руб. (сейчас {end})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"rs:pick:{dv['id']}:{supplier_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"supplier:view:{supplier_id}")])
    await message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("delivery:reschedule:"))
async def reschedule_start(callback: CallbackQuery):
    supplier_id = int(callback.data.split(":")[2])
    await _show_reschedule_list(callback.message, supplier_id)
    await callback.answer()


@router.callback_query(F.data.startswith("rs:pick:"))
async def reschedule_pick_delivery(callback: CallbackQuery, state: FSMContext):
    _, _, delivery_id, supplier_id = callback.data.split(":")
    await state.update_data(delivery_id=int(delivery_id), supplier_id=int(supplier_id))
    await state.set_state(RescheduleDelivery.date)
    today = date.today()
    await callback.message.edit_text(
        "📅 Выбери <b>новую дату</b> оплаты:",
        reply_markup=_date_picker_kb(today.year, today.month),
    )
    await callback.answer()


@router.callback_query(RescheduleDelivery.date, F.data.startswith("dp:nav:"))
async def reschedule_date_nav(callback: CallbackQuery, state: FSMContext):
    _, _, year, month = callback.data.split(":")
    await callback.message.edit_reply_markup(
        reply_markup=_date_picker_kb(int(year), int(month)),
    )
    await callback.answer()


@router.callback_query(RescheduleDelivery.date, F.data == "dp:today")
async def reschedule_date_today(callback: CallbackQuery, state: FSMContext):
    today = date.today()
    await callback.message.edit_reply_markup(
        reply_markup=_date_picker_kb(today.year, today.month),
    )
    await callback.answer()


@router.callback_query(RescheduleDelivery.date, F.data.startswith("dp:day:"))
async def reschedule_date_pick(callback: CallbackQuery, state: FSMContext):
    _, _, year, month, day = callback.data.split(":")
    new_date = f"{year}-{int(month):02d}-{int(day):02d}"
    data = await state.get_data()
    delivery_id = data["delivery_id"]
    supplier_id = data["supplier_id"]
    await set_manual_end_date(delivery_id, new_date)
    await state.clear()
    dv = await get_delivery(delivery_id)
    await callback.message.edit_text(
        f"✅ Дата оплаты поставки <b>#{delivery_id}</b> перенесена на <b>{new_date}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К поставщику", callback_data=f"supplier:view:{supplier_id}")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")],
        ]),
    )
    await callback.answer()
