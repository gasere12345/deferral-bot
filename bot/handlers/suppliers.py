from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from bot.db import add_supplier, get_all_suppliers, get_supplier, edit_supplier, delete_supplier, get_deliveries

router = Router()


class AddSupplier(StatesGroup):
    name = State()
    days = State()


class EditSupplier(StatesGroup):
    field = State()
    value = State()


def suppliers_list_keyboard(suppliers):
    kb = []
    for s in suppliers:
        kb.append([InlineKeyboardButton(
            text=s["name"],
            callback_data=f"supplier:view:{s['id']}",
        )])
    kb.append([InlineKeyboardButton(text="➕ Добавить", callback_data="supplier:add")])
    kb.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def supplier_detail_keyboard(supplier_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить поставку", callback_data=f"delivery:add:{supplier_id}")],
        [InlineKeyboardButton(text="📦 Поставки", callback_data=f"delivery:list:{supplier_id}")],
        [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"supplier:edit_menu:{supplier_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"supplier:delete:{supplier_id}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="supplier:list")],
    ])


@router.callback_query(F.data == "menu:suppliers")
async def show_suppliers_menu(callback: CallbackQuery):
    suppliers = await get_all_suppliers()
    if not suppliers:
        text = "📋 <b>Поставщики</b>\n\nПока нет ни одного поставщика. Нажми «➕ Добавить»."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data="supplier:add")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")],
        ])
    else:
        text = "📋 <b>Поставщики</b> — выбери из списка:"
        kb = suppliers_list_keyboard(suppliers)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "supplier:list")
async def show_suppliers_list(callback: CallbackQuery):
    suppliers = await get_all_suppliers()
    text = "📋 <b>Поставщики</b> — выбери из списка:"
    await callback.message.edit_text(text, reply_markup=suppliers_list_keyboard(suppliers))
    await callback.answer()


@router.callback_query(F.data == "supplier:add")
async def add_supplier_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddSupplier.name)
    await callback.message.edit_text(
        "✏️ Введите <b>название поставщика</b>:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="menu:suppliers")],
        ]),
    )
    await callback.answer()


@router.message(AddSupplier.name)
async def add_supplier_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое. Введите ещё раз:")
        return
    await state.update_data(name=name)
    await state.set_state(AddSupplier.days)
    await message.answer(
        f"⏳ Сколько дней отсрочки у <b>{name}</b>? (число)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="menu:suppliers")],
        ]),
    )


@router.message(AddSupplier.days)
async def add_supplier_days(message: types.Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите целое положительное число (дни отсрочки):")
        return
    data = await state.get_data()
    name = data["name"]
    ok = await add_supplier(name, days)
    await state.clear()
    if ok:
        text = f"✅ Поставщик <b>{name}</b> добавлен (отсрочка {days} дн.)"
    else:
        text = f"⚠️ Поставщик <b>{name}</b> уже существует!"
    suppliers = await get_all_suppliers()
    await message.answer(text, reply_markup=suppliers_list_keyboard(suppliers))


@router.callback_query(F.data.startswith("supplier:view:"))
async def view_supplier(callback: CallbackQuery):
    supplier_id = int(callback.data.split(":")[2])
    s = await get_supplier(supplier_id)
    if not s:
        await callback.answer("Поставщик не найден", show_alert=True)
        return
    deliveries = await get_deliveries(supplier_id=supplier_id)
    total = len(deliveries)
    unpaid = sum(1 for d in deliveries if not d["paid"])
    text = (
        f"📋 <b>{s['name']}</b>\n"
        f"⏳ Отсрочка: {s['deferral_days']} дн.\n"
        f"📦 Поставок: {total} | Не оплачено: {unpaid}"
    )
    await callback.message.edit_text(text, reply_markup=supplier_detail_keyboard(supplier_id))
    await callback.answer()


@router.callback_query(F.data.startswith("supplier:edit_menu:"))
async def edit_supplier_menu(callback: CallbackQuery):
    supplier_id = int(callback.data.split(":")[2])
    s = await get_supplier(supplier_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Название", callback_data=f"supplier:edit_name:{supplier_id}")],
        [InlineKeyboardButton(text="✏️ Дни отсрочки", callback_data=f"supplier:edit_days:{supplier_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"supplier:view:{supplier_id}")],
    ])
    await callback.message.edit_text(
        f"✏️ <b>Редактирование</b> «{s['name']}»\nЧто меняем?",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("supplier:edit_name:"))
async def edit_supplier_name_start(callback: CallbackQuery, state: FSMContext):
    supplier_id = int(callback.data.split(":")[2])
    await state.update_data(supplier_id=supplier_id, field="name")
    await state.set_state(EditSupplier.value)
    await callback.message.edit_text("✏️ Введите новое название:")
    await callback.answer()


@router.callback_query(F.data.startswith("supplier:edit_days:"))
async def edit_supplier_days_start(callback: CallbackQuery, state: FSMContext):
    supplier_id = int(callback.data.split(":")[2])
    await state.update_data(supplier_id=supplier_id, field="deferral_days")
    await state.set_state(EditSupplier.value)
    await callback.message.edit_text("✏️ Введите новое количество дней отсрочки:")
    await callback.answer()


@router.message(EditSupplier.value)
async def edit_supplier_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    supplier_id = data["supplier_id"]
    field = data["field"]
    value = message.text.strip()
    if field == "deferral_days":
        try:
            value = int(value)
            if value <= 0:
                raise ValueError
        except ValueError:
            await message.answer("Введите целое положительное число:")
            return
    await edit_supplier(supplier_id, **{field: value})
    await state.clear()
    s = await get_supplier(supplier_id)
    await message.answer(
        f"✅ Обновлено!",
        reply_markup=supplier_detail_keyboard(supplier_id),
    )


@router.callback_query(F.data.startswith("supplier:delete:"))
async def delete_supplier_confirm(callback: CallbackQuery):
    supplier_id = int(callback.data.split(":")[2])
    s = await get_supplier(supplier_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"supplier:delete_yes:{supplier_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"supplier:view:{supplier_id}")],
    ])
    await callback.message.edit_text(
        f"🗑 Удалить <b>{s['name']}</b>?\nВсе поставки этого поставщика тоже будут удалены.",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("supplier:delete_yes:"))
async def delete_supplier_execute(callback: CallbackQuery):
    supplier_id = int(callback.data.split(":")[2])
    s = await get_supplier(supplier_id)
    name = s["name"]
    await delete_supplier(supplier_id)
    await callback.answer(f"🗑 «{name}» удалён", show_alert=True)
    await show_suppliers_menu(callback)
