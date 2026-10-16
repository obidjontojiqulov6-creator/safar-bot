import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
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
    
    # Avvalgi klaviaturalarni olib tashlab, til tanlashni chiqaramiz
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

    await state.update_data(to_city=message.text)
    await state.set_state(BookingState.waiting_for_passengers)

    builder = ReplyKeyboardBuilder()
    builder.button(text="1")
    builder.button(text="2")
    builder.button(text="3")
    builder.button(text="4")
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(2, 2, 1)

    text = "👥 Necha kishilik joy kerak? (Odam sonini tanlang):" if lang == "uz" else "👥 Сколько мест нужно? (Выберите количество пассажиров):"
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_passengers, F.text.in_(["1", "2", "3", "4"]))
async def select_passengers(message: types.Message, state: FSMContext):
    await state.update_data(passengers=message.text)
    await state.set_state(BookingState.waiting_for_price)

    data = await state.get_data()
    lang = data.get("lang", "uz")

    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(1)

    text = (
        "💵 Yo'lkira uchun bermoqchi bo'lgan summangizni kiriting (masalan: `50000` yoki `80000` so'm):"
        if lang == "uz" else
        "💵 Введите сумму, которую готовы предложить за поездку (например: `50000` или `80000` сум):"
    )
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(BookingState.waiting_for_price)
async def enter_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_passengers)
        builder = ReplyKeyboardBuilder()
        for i in ["1", "2", "3", "4"]:
            builder.button(text=i)
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(2, 2, 1)
        text = "👥 Necha kishilik joy kerak?" if lang == "uz" else "👥 Сколько мест нужно?"
        return await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

    await state.update_data(price=message.text)
    await state.set_state(BookingState.waiting_for_contact)

    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Kontaktni yuborish" if lang == "uz" else "📱 Отправить контакт", request_contact=True)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(1, 1)

    text = (
        "📞 Aloqa uchun telefon raqamingizni yuboring (tugmani bosing yoki raqamni yozing):"
        if lang == "uz" else
        "📞 Отправьте номер телефона для связи (нажмите кнопку или напишите номер):"
    )
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_contact)
async def get_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_price)
        builder = ReplyKeyboardBuilder()
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        text = "💵 Summani qaytadan kiriting:" if lang == "uz" else "💵 Введите сумму заново:"
        return await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

    phone = message.contact.phone_number if message.contact else message.text
    name = message.from_user.first_name

    if lang == "uz":
        response_text = (
            f"Rahmat, {name}! Buyurtmangiz qabul qilindi ✅\n\n"
            f"📋 **Buyurtma tafsilotlari:**\n"
            f"📍 Qayerdan: {data.get('from_city')}\n"
            f"🏁 Qayerga: {data.get('to_city')}\n"
            f"👥 Odam soni: {data.get('passengers')} ta\n"
            f"💵 Taklif qilingan narx: {data.get('price')}\n"
            f"📞 Tel raqam: `{phone}`\n\n"
            "Tez orada haydovchilarimiz siz bilan bog'lanishadi."
        )
    else:
        response_text = (
            f"Спасибо, {name}! Ваш заказ принят ✅\n\n"
            f"📋 **Детали заказа:**\n"
            f"📍 Откуда: {data.get('from_city')}\n"
            f"🏁 Куда: {data.get('to_city')}\n"
            f"👥 Количество пассажиров: {data.get('passengers')}\n"
            f"💵 Предложенная цена: {data.get('price')}\n"
            f"📞 Телефон: `{phone}`\n\n"
            "Скоро наши водители свяжутся с вами."
        )

    await message.answer(response_text, reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
    await state.clear()

@dp.message()
async def echo_text(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

async def handle(request):
    return web.Response(text="Bot ishlayapti!")

async def web_server():
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot ishga tushdi...")
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
