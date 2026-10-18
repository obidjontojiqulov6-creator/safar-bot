import os
import asyncio
import logging
import math
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Vaqtinchalik xotira (Keyinchalik bazaga o'tkazamiz)
ORDERS = {}    # Faol buyurtmalar: {order_id: {user_id, from_city, to_city, passengers, price, phone, lat, lon}}
DRIVERS = {}   # Haydovchilar: {driver_id: {name, car, lat, lon, balance}}

class BookingState(StatesGroup):
    waiting_for_lang = State()
    waiting_for_from_city = State()
    waiting_for_to_city = State()
    waiting_for_passengers = State()
    waiting_for_price = State()
    waiting_for_contact = State()

class DriverState(StatesGroup):
    waiting_for_car = State()
    waiting_for_location = State()

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
    builder.button(text="🚖 Haydovchi bo'lish")
    builder.adjust(2, 1)
    
    await message.answer(
        "Assalomu alaykum! Safar taksi xizmatiga xush kelibsiz.\n"
        "Tilni tanlang yoki haydovchi sifatida kiring:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.message(F.text == "🚖 Haydovchi bo'lish")
async def driver_mode(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(DriverState.waiting_for_car)
    await message.answer(
        "🚖 Haydovchilar bo'limiga xush kelibsiz!\n"
        "Mashinangiz rusumi va raqamini kiriting (masalan: `Cobalt 01 A 777 AA`):",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

@dp.message(DriverState.waiting_for_car)
async def get_driver_car(message: types.Message, state: FSMContext):
    await state.update_data(car=message.text)
    await state.set_state(DriverState.waiting_for_location)

    builder = ReplyKeyboardBuilder()
    builder.button(text="📍 Lokatsiyani yuborish", request_location=True)
    builder.adjust(1)

    await message.answer(
        "Rahmat! Endi haydovchilar bazasiga qo'shilish uchun turgan joyingizni (lokatsiyangizni) yuboring:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.message(DriverState.waiting_for_location, F.location)
async def get_driver_location(message: types.Message, state: FSMContext):
    data = await state.get_data()
    driver_id = message.from_user.id
    
    DRIVERS[driver_id] = {
        "name": message.from_user.first_name,
        "car": data.get("car"),
        "lat": message.location.latitude,
        "lon": message.location.longitude,
        "balance": 10000  # Boshlang'ich bonus balans
    }

    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Yangi buyurtmalar")
    builder.button(text="💰 Balansni tekshirish")
    builder.adjust(2)

    await message.answer(
        "✅ Siz muvaffaqiyatli haydovchilar safiga qo'shildingiz!\n"
        "Yaqin atrofdagi buyurtmalarni ko'rish uchun pastdagi tugmani bosing:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await state.clear()

@dp.message(F.text == "📋 Yangi buyurtmalar")
async def show_available_orders(message: types.Message):
    driver_id = message.from_user.id
    if driver_id not in DRIVERS:
        return await message.answer("Iltimos, avval /start tugmasini bosib haydovchi sifatida ro'yxatdan o'ting.")

    if not ORDERS:
        return await message.answer("Hozircha faol buyurtmalar mavjud emas. Birozdan so'ng yana tekshiring.")

    driver = DRIVERS[driver_id]
    
    for order_id, order in ORDERS.items():
        # Masofani hisoblash (taxminiy km)
        distance = math.sqrt((driver['lat'] - order['lat'])**2 + (driver['lon'] - order['lon'])**2) * 111
        
        # Rangli indikatorlar (10km gacha yashil, undan uzoq qizil)
        indicator = "🟢 Yaqin" if distance <= 10 else "🔴 Uzoqroq"
        
        text = (
            f"🚖 **Buyurtma #{order_id}**\n"
            f"📍 Qayerdan: {order['from_city']}\n"
            f"🏁 Qayerga: {order['to_city']}\n"
            f"👥 Yo'lovchilar: {order['passengers']}\n"
            f"💵 Narx: {order['price']}\n"
            f"📏 Masofa: ~{round(distance, 1)} km ({indicator})"
        )
        
        inline_builder = InlineKeyboardBuilder()
        inline_builder.button(text="📞 Kontaktni ochish (Komissiya: 2000 so'm)", callback_data=f"open_contact_{order_id}")
        
        await message.answer(text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("open_contact_"))
async def open_contact_callback(callback: types.CallbackQuery):
    driver_id = callback.from_user.id
    order_id = callback.data.split("_")[2]

    if driver_id not in DRIVERS:
        return await callback.answer("Siz haydovchi sifatida ro'yxatdan o'tmagansiz!", show_alert=True)

    if order_id not in ORDERS:
        return await callback.answer("Bu buyurtma allaqachon yopilgan yoki mavjud emas!", show_alert=True)

    driver = DRIVERS[driver_id]
    if driver["balance"] < 2000:
        return await callback.answer("Balansingiz yetarli emas! Iltimos, balansni to'ldiring.", show_alert=True)

    # Balansdan komissiya yechish
    driver["balance"] -= 2000
    order = ORDERS[order_id]

    contact_text = (
        f"✅ Buyurtma muvaffaqiyatli ochildi!\n"
        f"👤 Yo'lovchi: {order['name']}\n"
        f"📞 Telefon: `+{order['phone']}`\n"
        f"💰 Qolgan balansingiz: {driver['balance']} so'm"
    )
    await callback.message.answer(contact_text, parse_mode="Markdown")
    await callback.answer()

@dp.message(F.text == "💰 Balansni tekshirish")
async def check_balance(message: types.Message):
    driver_id = message.from_user.id
    if driver_id not in DRIVERS:
        return await message.answer("Siz ro'yxatdan o'tmagansiz.")
    
    balance = DRIVERS[driver_id]["balance"]
    await message.answer(f"💳 Sizning balansingiz: **{balance} so'm**", parse_mode="Markdown")

# Yo'lovchi qismi (Oldingi mantiq)
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
            if city != data.get("from_city"):
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
        if lang == "uz" else
        f"👥 Выберите состав пассажиров (Максимум 4):\nТекущие: {pass_str}"
    )
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_passengers)
async def handle_passengers(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    passengers = data.get("passengers", [])

    text = message.text

    if text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_to_city)
        builder = ReplyKeyboardBuilder()
        for city in CITIES:
            if city != data.get("from_city"):
                builder.button(text=city)
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(2, 2, 2, 2, 2, 2, 1)
        return await message.answer("🏁 Qayerga borasiz?", reply_markup=builder.as_markup(resize_keyboard=True))

    if text in ["🔄 Tozalash", "🔄 Очистить"]:
        passengers = []
        await state.update_data(passengers=passengers)
        return await show_passenger_menu(message, passengers, lang)

    if text in ["➡️ Keyingi bo'lim", "➡️ Следующий раздел"]:
        if not passengers:
            err = "Iltimos, kamida 1 ta yo'lovchini tanlang!" if lang == "uz" else "Пожалуйста, выберите хотя бы 1 пассажира!"
            return await message.answer(err)
        
        await state.set_state(BookingState.waiting_for_price)
        builder = ReplyKeyboardBuilder()
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(1)
        
        price_text = (
            "💵 Yo'lkira uchun bermoqchi bo'lgan summangizni kiriting (masalan: `50000` so'm):"
            if lang == "uz" else
            "💵 Введите сумму, которую готовы предложить за поездку (например: `50000` сум):"
        )
        return await message.answer(price_text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

    if text in ["👨 Erkak", "👨 Мужчина", "👩 Ayol", "👩 Женщина"]:
        if len(passengers) >= 4:
            warn = "Maksimal 4 ta yo'lovchi tanlash mumkin!" if lang == "uz" else "Максимум можно выбрать 4 пассажиров!"
            return await message.answer(warn)
        
        emoji = "👨" if "Erkak" in text or "Мужчина" in text else "👩"
        passengers.append(emoji)
        await state.update_data(passengers=passengers)
        return await show_passenger_menu(message, passengers, lang)
    
    await message.answer("Iltimos, pastdagi tugmalardan foydalaning.")

@dp.message(BookingState.waiting_for_price)
async def enter_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_passengers)
        return await show_passenger_menu(message, data.get("passengers", []), lang)

    await state.update_data(price=message.text)
    await state.set_state(BookingState.waiting_for_contact)

    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Kontaktni yuborish" if lang == "uz" else "📱 Отправить контакт", request_contact=True)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(1, 1)

    text = (
        "📞 Iltimos, aloqa uchun pastdagi **'📱 Kontaktni yuborish'** tugmasini bosing:"
        if lang == "uz" else
        "📞 Пожалуйста, нажмите кнопку **'📱 Отправить контакт'** ниже:"
    )
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(BookingState.waiting_for_contact, F.contact)
async def get_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    phone = message.contact.phone_number
    name = message.from_user.first_name
    pass_summary = " ".join(data.get('passengers', []))

    # Buyurtmani umumiy bazaga saqlaymiz (Toshkent koordinatasini vaqtincha default olamiz)
    order_id = str(len(ORDERS) + 1)
    ORDERS[order_id] = {
        "user_id": message.from_user.id,
        "name": name,
        "from_city": data.get('from_city'),
        "to_city": data.get('to_city'),
        "passengers": pass_summary,
        "price": data.get('price'),
        "phone": phone,
        "lat": 41.2995,  # Keyinchalik haqiqiy lokatsiya olinadi
        "lon": 69.2401
    }

    if lang == "uz":
        response_text = (
            f"Rahmat, {name}! Buyurtmangiz qabul qilindi ✅\n\n"
            f"📋 **Buyurtma tafsilotlari:**\n"
            f"📍 Qayerdan: {data.get('from_city')}\n"
            f"🏁 Qayerga: {data.get('to_city')}\n"
            f"👥 Odamlar: {pass_summary}\n"
            f"💵 Taklif qilingan narx: {data.get('price')}\n"
            f"📞 Tel raqam: `+{phone}`\n\n"
            "Tez orada haydovchilarimiz siz bilan bog'lanishadi."
        )
        cancel_btn_text = "❌ Buyurtmani bekor qilish / Qaytadan"
    else:
        response_text = (
            f"Спасибо, {name}! Ваш заказ принят ✅\n\n"
            f"📋 **Детали заказа:**\n"
            f"📍 Откуда: {data.get('from_city')}\n"
            f"🏁 Куда: {data.get('to_city')}\n"
            f"👥 Пассажиры: {pass_summary}\n"
            f"💵 Предложенная цена: {data.get('price')}\n"
            f"📞 Телефон: `+{phone}`\n\n"
            "Скоро наши водители свяжутся с вами."
        )
        cancel_btn_text = "❌ Отменить заказ / Заново"

    inline_builder = InlineKeyboardBuilder()
    inline_builder.button(text=cancel_btn_text, callback_data=f"cancel_order_{order_id}")

    await message.answer(response_text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")
    await state.clear()

@dp.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order_callback(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.split("_")[2]
    if order_id in ORDERS:
        del ORDERS[order_id]

    await callback.answer("Buyurtma bekor qilindi!")
    await state.set_state(BookingState.waiting_for_from_city)
    lang = "uz"

    builder = ReplyKeyboardBuilder()
    for city in CITIES:
        builder.button(text=city)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(2, 2, 2, 2, 2, 2, 1)

    text = "❌ Buyurtma bekor qilindi.\n\n📍 Qayerdan jo'naysiz? Hududni tanlang:" if lang == "uz" else "❌ Заказ отменен.\n\n📍 Откуда выезжаете? Выберите регион:"
    
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await callback.message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_contact)
async def wrong_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_price)
        builder = ReplyKeyboardBuilder()
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        return await message.answer("💵 Summani qaytadan kiriting:", reply_markup=builder.as_markup(resize_keyboard=True))

    err = (
        "⚠️ Iltimos, qo'lda raqam yozmang, faqat pastdagi '📱 Kontaktni yuborish' tugmasini bosing!"
        if lang == "uz" else
        "⚠️ Пожалуйста, не пишите номер вручную, нажмите кнопку '📱 Отправить контакт' ниже!"
    )
    await message.answer(err)

@dp.message()
async def echo_text(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

async def handle(request):
    return web.Response(text="Bot uyg'oq va ishlayapti!")

async def self_ping():
    await asyncio.sleep(10)
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if not render_url:
        return
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(render_url) as response:
                    pass
        except Exception:
            pass
        await asyncio.sleep(420)

async def web_server():
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    asyncio.create_task(self_ping())

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot haydovchilar rejimi bilan ishga tushdi...")
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.main() if hasattr(asyncio, "main") else asyncio.run(main())
