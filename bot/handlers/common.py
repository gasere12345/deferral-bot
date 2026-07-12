from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Поставщики", callback_data="menu:suppliers")],
        [InlineKeyboardButton(text="📦 Поставки", callback_data="menu:deliveries")],
        [InlineKeyboardButton(text="📅 Календарь", callback_data="menu:calendar")],
        [InlineKeyboardButton(text="💰 Сегодня к оплате", callback_data="menu:today")],
    ])


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Добро пожаловать в <b>Deferral Bot</b>\n\n"
        "Я помогу отслеживать отсрочки платежей поставщикам.\n"
        "Выбирай нужный раздел:",
        reply_markup=main_menu(),
    )


@router.callback_query(lambda c: c.data == "menu:main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "👋 Главное меню. Выбирай:",
        reply_markup=main_menu(),
    )
    await callback.answer()
