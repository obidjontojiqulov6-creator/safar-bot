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

# Bot bosqichlari (Holatlari)
class BookingState(StatesGroup):
    waiting_for_passengers = State()
    waiting_for_car_type = State()
    waiting_for_contact = State()

# /start buyrug'i
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚕 Toshkent ➔ Andijon")
    builder.button(text="🚕 Andijon ➔ Toshkent")
    builder.button(text="📞 Operator bilan bog'lanish")
    builder.adjust(2, 1)
    
    await message.answer(
        "Assalomu alaykum! Safar taksi xizmatiga xush kelibsiz.\n"
        "Buyurtma berish uchun quyidagi yo'nalishlardan birini tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Yo'nalish tanlanganda: Odam sonini so'rash
@dp.message(F.text.in_(["🚕 Toshkent ➔ Andijon", "🚕 Andijon ➔ Toshkent"]))
async def select_route(message: types.Message, state: FSMContext):
    await state.update_data(route=message.text)
    await state.set_state(BookingState.waiting_for_passengers)

    builder = ReplyKeyboardBuilder()
    builder.button(text="1")
    builder.button(text="2")
    builder.button(text="3")
    builder.button(text="4")
    builder.button(text="🔙 Orqaga")
    builder.adjust(2, 2, 1)

    await message.answer(
        f"✅ Siz **{message.text}** yo'nalishini tanladingiz.\n\n"
        "Necha kishilik joy kerak? Quyidagilardan birini tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="Markdown"
    )

# Odam soni tanlanganda: Mashina turini so'rash
@dp.message(BookingState.waiting_for_passengers, F.text.in_(["1", "2", "3", "4"]))
async def select_passengers(message: types.Message, state: FSMContext):
    await state.update_data(passengers=message.text)
    await state.set_state(BookingState.waiting_for_car_type)

    builder = ReplyKeyboardBuilder()
    builder.button(text="🚗 Oddiy")
    builder.button(text="🚙 O'rta")
    builder.button(text="⭐ Komfort")
    builder.button(text="🔙 Orqaga")
    builder.adjust(2, 1, 1)

    await message.answer(
        f"👥 Yo'lovchilar soni: **{message.text} ta**.\n\n"
        "Qanday mashina kerak? Quyidagi turlardan birini tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="Markdown"
    )

# Mashina turi tanlanganda: Telefon raqam so'rash
@dp.message(BookingState.waiting_for_car_type, F.text.in_(["🚗 Oddiy", "🚙 O'rta", "⭐ Komfort"]))
async def select_car_type(message: types.Message, state: FSMContext):
    await state.update_data(car_type=message.text)
    await state.set_state(BookingState.waiting_for_contact)

    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Kontaktni yuborish", request_contact=True)
    builder.button(text="🔙 Orqaga")
    builder.adjust(1, 1)

    await message.answer(
        f"🚘 Tanlangan mashina turi: **{message.text}**.\n\n"
        "Iltimos, pastdagi tugmani bosib telefon raqamingizni yuboring:",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="Markdown"
    )

# Operator bilan bog'lanish
@dp.message(F.text == "📞 Operator bilan bog'lanish")
async def contact_operator(message: types.Message):
    await message.answer(
        "📞 Operator bilan bog'lanish uchun:\n"
        "Admin: @Safar_Admin\n"
        "Telefon: +998 90 000-00-00"
    )

# Orqaga qaytish tugmasi
@dp.message(F.text == "🔙 Orqaga")
async def go_back(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

# Kontakt qabul qilinganda buyurtmani yakunlash
@dp.message(BookingState.waiting_for_contact, F.contact)
async def get_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    route = data.get("route")
    passengers = data.get("passengers")
    car_type = data.get("car_type")
    
    phone = message.contact.phone_number
    name = message.from_user.first_name

    await message.answer(
        f"Rahmat, {name}! Buyurtmangiz muvaffaqiyatli qabul qilindi ✅\n\n"
        f"📋 **Buyurtma tafsilotlari:**\n"
        f"▫️ Yo'nalish: {route}\n"
        f"▫️ Odam soni: {passengers} ta\n"
        f"▫️ Mashina turi: {car_type}\n"
        f"▫️ Tel raqam: `{phone}`\n\n"
        "Tez orada haydovchi yoki operatorimiz siz bilan bog'lanadi.",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.clear()

# Boshqa holatlardagi xabarlar uchun
@dp.message()
async def echo_text(message: types.Message):
    await message.answer("Iltimos, tugmalardan foydalaning yoki /start buyrug'ini bosing.")

# Render uchun veb-server
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
