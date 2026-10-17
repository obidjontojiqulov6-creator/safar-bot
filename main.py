import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

class BookingState(StatesGroup):
    waiting_for_lang = State()
    waiting_for_from_city = State()
    waiting_for_to_city = State()
    waiting_for_passengers = State()
    waiting_for_price = State()
    waiting_for_contact = State()

CITIES = [
    "Toshkent", "Andijon", "Buxoro", "Jizzax", 
    "Navoiy", "Namangan", "Qarshi", "Samarqand", 
    "Guliston", "Termiz", "Urganch", "Nukus"
]

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BookingState.waiting_for_lang)
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha")
    builder.button(text="🇷🇺 Русский")
    builder.adjust(2)
    
    await message.answer(
        "Assalomu alaykum! Safar taksi xizmatiga xush kelibsiz.\n"
        "Tilni tanlang / Пожалуйста, выберите язык:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.message(BookingState.waiting_for_lang, F.text.in_(["🇺🇿 O'zbekcha", "🇷🇺 Русский"]))
async def select_language(message: types.Message, state: FSMContext):
    lang = "uz" if "O'zbekcha" in message.text else "ru"
    await state.update_data(lang=lang)
    await state.set_state(BookingState.waiting_for_from_city)

    builder = ReplyKeyboardBuilder()
    for city in CITIES:
        builder.button(text=city)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(2, 2, 2, 2, 2, 2, 1)

    text = "📍 Qayerdan jo'naysiz? Hududni tanlang:" if lang == "uz" else "📍 Откуда выезжаете? Выберите регион:"
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_from_city)
async def select_from_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        return await cmd_start(message, state)
    
    if message.text not in CITIES:
        err = "Iltimos, tugmalardagi hududlardan birini tanlang." if lang == "uz" else "Пожалуйста, выберите регион с помощью кнопок."
        return await message.answer(err)

    await state.update_data(from_city=message.text)
    await state.set_state(BookingState.waiting_for_to_city)

    builder = ReplyKeyboardBuilder()
    for city in CITIES:
        if city != message.text:
            builder.button(text=city)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(2, 2, 2, 2, 2, 2, 1)

    text = f"🏁 Qayerga borasiz? (Jo'nash: {message.text})" if lang == "uz" else f"🏁 Куда едем? (Откуда: {message.text})"
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_to_city)
async def select_to_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_from_city)
        builder = ReplyKeyboardBuilder()
        for city in CITIES:
            builder.button(text=city)
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(2, 2, 2, 2, 2, 2, 1)
        text = "📍 Qayerdan jo'naysiz? Hududni tanlang:" if lang == "uz" else "📍 Откуда выезжаете? Выберите регион:"
        return await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

    if message.text not in CITIES:
        err = "Iltimos, ro'yxatdagi hududlardan birini tanlang." if lang == "uz" else "Пожалуйста, выберите регион из списка."
        return await message.answer(err)

    await state.update_data(to_city=message.text, passengers=[])
    await state.set_state(BookingState.waiting_for_passengers)

    await show_passenger_menu(message, [], lang)

async def show_passenger_menu(message: types.Message, passengers: list, lang: str):
    builder = ReplyKeyboardBuilder()
    builder.button(text="👨 Erkak" if lang == "uz" else "👨 Мужчина")
    builder.button(text="👩 Ayol" if lang == "uz" else "👩 Женщина")
    builder.button(text="🔄 Tozalash" if lang == "uz" else "🔄 Очистить")
    builder.button(text="➡️ Keyingi bo'lim" if lang == "uz" else "➡️ Следующий раздел")
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(2, 2, 1)

    pass_str = " ".join(passengers) if passengers else ("(Hali tanlanmadi)" if lang == "uz" else "(Еще не выбрано)")
    text = (
        f"👥 Yo'lovchilar tarkibini tanlang (Maksimal 4 ta):\nJoriy: {pass_str}"
