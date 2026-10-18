import os
import asyncio
import logging
import math
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

ORDERS = {}       
DRIVERS = {}      
ALL_USERS = set()
DAILY_VISITS = set()
LAST_VISIT_DATE = datetime.now().date()

ADMIN_ID = 123456789  # O'z ID raqamingizni yozing

class BookingState(StatesGroup):
    waiting_for_lang = State()
    waiting_for_role = State()        
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
    user_id = message.from_user.id
    ALL_USERS.add(user_id)
    
    global DAILY_VISITS, LAST_VISIT_DATE
    current_date = datetime.now().date()
    if current_date != LAST_VISIT_DATE:
        DAILY_VISITS.clear()
        LAST_VISIT_DATE = current_date
    DAILY_VISITS.add(user_id)

    await state.clear()
    await state.set_state(BookingState.waiting_for_lang)
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha")
    builder.button(text="🇷🇺 Русский")
    
    if user_id == ADMIN_ID:
        builder.button(text="👑 Admin paneli")
        builder.adjust(2, 1)
    else:
        builder.adjust(2)
    
    welcome_text = (
        "🇺🇿 Assalomu alaykum! Safar taksi xizmatiga xush kelibsiz. Iltimos, tilni tanlang:\n\n"
        "🇷🇺 Здравствуйте! Добро пожаловать в службу такси Safar. Пожалуйста, выберите язык:"
    )
    
    await message.answer(welcome_text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(F.text == "👑 Admin paneli")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Sizda bu bo'limga kirish huquqi yo'q.")
    
    total_users = len(ALL_USERS)
    today_active = len(DAILY_VISITS)
    total_orders = len(ORDERS)
    total_drivers = len(DRIVERS)

    text = (
        f"👑 **Rahbar / Admin paneli**\n\n"
        f"👥 Jami a'zo bo'lgan foydalanuvchilar: **{total_users} ta**\n"
        f"📅 Bugun botga kirganlar: **{today_active} ta**\n"
        f"📋 Faol buyurtmalar: **{total_orders} ta**\n"
        f"🚖 Ro'yxatdan o'tgan haydovchilar: **{total_drivers} ta**"
    )
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔄 Statistikani yangilash")
    builder.button(text="🏠 Asosiy menyu")
    builder.adjust(1, 1)
    
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(F.text == "🔄 Statistikani yangilash")
async def refresh_stats(message: types.Message):
    await admin_panel(message)

@dp.message(F.text.in_(["🏠 Asosiy menyu", "🏠 Главное меню"]))
async def back_to_main(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

# --- TIL VA ROLNI TANLASH ---
@dp.message(BookingState.waiting_for_lang, F.text.in_(["🇺🇿 O'zbekcha", "🇷🇺 Русский"]))
async def select_language(message: types.Message, state: FSMContext):
    lang = "uz" if "O'zbekcha" in message.text else "ru"
    await state.update_data(lang=lang)
    await state.set_state(BookingState.waiting_for_role)

    builder = ReplyKeyboardBuilder()
    if lang == "uz":
        builder.button(text="👤 Yo'lovchi")
        builder.button(text="🚖 Haydovchi kabineti")
        text = "Siz kimsiz? Iltimos, o'z rolingizni tanlang:"
    else:
        builder.button(text="👤 Пассажир")
        builder.button(text="🚖 Кабинет водителя")
        text = "Кто вы? Пожалуйста, выберите свою роль:"
    
    builder.adjust(2)
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_role)
async def select_role(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    text = message.text

    if text in ["👤 Yo'lovchi", "👤 Пассажир"]:
        await state.set_state(BookingState.waiting_for_from_city)
        builder = ReplyKeyboardBuilder()
        for city in CITIES:
            builder.button(text=city)
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(2, 2, 2, 2, 2, 2, 1)

        city_text = "📍 Qayerdan jo'naysiz? Hududni tanlang:" if lang == "uz" else "📍 Откуда выезжаете? Выберите регион:"
        return await message.answer(city_text, reply_markup=builder.as_markup(resize_keyboard=True))

    elif text in ["🚖 Haydovchi kabineti", "🚖 Кабинет водителя"]:
        driver_id = message.from_user.id
        
        if driver_id not in DRIVERS:
            # Render'dagi web ilovamizga havola
            # Eslatma: Render'ga joylagach, URL manzil avtomatik ishlaydi
            render_url = os.getenv("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
            webapp_url = f"{render_url}/driver-form?lang={lang}&user_id={driver_id}"
            
            inline_builder = InlineKeyboardBuilder()
            inline_builder.button(
                text="📝 Anketani to'ldirish (Mini App)" if lang == "uz" else "📝 Заполнить анкету (Mini App)",
                web_app=types.WebAppInfo(url=webapp_url)
            )
            
            intro_text = (
                "🚖 **Haydovchi kabineti**\n\n"
                "Ro'yxatdan o'tish uchun pastdagi chiroyli tugmani bosing va anketa ma'lumotlarini (ism, tel, mashina va rasm) to'ldiring:"
                if lang == "uz" else
                "🚖 **Кабинет водителя**\n\n"
                "Для регистрации нажмите на кнопку ниже и заполни форму (имя, телефон, машина и фото):"
            )
            return await message.answer(intro_text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")
        else:
            DRIVERS[driver_id]["lang"] = lang
            return await show_driver_menu(message)
    
    else:
        err = "Iltimos, tugmalardan birini tanlang!" if lang == "uz" else "Пожалуйста, выберите с помощью кнопок!"
        return await message.answer(err)

# --- MINI APP ORQALI KELGAN MA'LUMOTLARNI QABUL QILISH ---
@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        driver_id = message.from_user.id
        
        DRIVERS[driver_id] = {
            "name": data.get("name"),
            "phone": data.get("phone"),
            "car": data.get("car"),
            "photo": data.get("photo", ""), # Mashina rasmi havolasi
            "current_city": data.get("from_city"),
            "target_city": data.get("to_city"),
            "lat": 41.2995,
            "lon": 69.2401,
            "balance": 10000,
            "lang": data.get("lang", "uz")
        }

        await message.answer("✅ Tabriklaymiz! Ro'yxatdan muvaffaqiyatli o'tdingiz.")
        await show_driver_menu(message)
    except Exception as e:
        await message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

# --- HAYDOVCHI MENYUSI VA TUGMALARI ---
async def show_driver_menu(message: types.Message):
    driver_id = message.from_user.id
    driver = DRIVERS[driver_id]
    lang = driver.get("lang", "uz")
    
    builder = ReplyKeyboardBuilder()
    if lang == "uz":
        builder.button(text="📋 Mos buyurtmalar")
        builder.button(text="🔄 Yo'nalishni o'zgartirish")
        builder.button(text="💰 Balansni tekshirish")
        builder.button(text="📍 Lokatsiyani yangilash", request_location=True)
        builder.button(text="🏠 Asosiy menyu")
        text = (
            f"🚖 **Haydovchi kabineti**\n\n"
            f"👤 Ism: {driver['name']}\n"
            f"📞 Tel: `+{driver['phone']}`\n"
            f"🚗 Mashina: {driver['car']}\n"
            f"📍 Turgan joyi: **{driver['current_city']}** ➔ Boradigan joyi: **{driver['target_city']}**\n"
            f"💳 Balans: {driver['balance']} so'm"
        )
    else:
        builder.button(text="📋 Подходящие заказы")
        builder.button(text="🔄 Изменить маршрут")
        builder.button(text="💰 Проверить баланс")
        builder.button(text="📍 Обновить локацию", request_location=True)
        builder.button(text="🏠 Главное меню")
        text = (
            f"🚖 **Кабинет водителя**\n\n"
            f"👤 Имя: {driver['name']}\n"
            f"📞 Тел: `+{driver['phone']}`\n"
            f"🚗 Машина: {driver['car']}\n"
            f"📍 Откуда: **{driver['current_city']}** ➔ Куда: **{driver['target_city']}**\n"
            f"💳 Баланс: {driver['balance']} сум"
        )
        
    builder.adjust(2, 1, 1, 1)
    
    if driver.get("photo") and driver["photo"].startswith("http"):
        await message.answer_photo(driver["photo"], caption=text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(F.location)
async def update_driver_location_anytime(message: types.Message):
    driver_id = message.from_user.id
    if driver_id in DRIVERS:
        DRIVERS[driver_id]["lat"] = message.location.latitude
        DRIVERS[driver_id]["lon"] = message.location.longitude
        lang = DRIVERS[driver_id].get("lang", "uz")
        
        upd_text = "📍 Lokatsiyangiz yangilandi!" if lang == "uz" else "📍 Локация обновлена!"
        await message.answer(upd_text)
        await show_driver_menu(message)

@dp.message(F.text.in_(["💰 Balansni tekshirish", "💰 Проверить баланс"]))
async def check_balance_btn(message: types.Message):
    driver_id = message.from_user.id
    if driver_id not in DRIVERS:
        return await message.answer("Siz haydovchi emassiz!")
    driver = DRIVERS[driver_id]
    lang = driver.get("lang", "uz")
    balance = driver["balance"]
    
    bal_text = f"💳 Sizning balansingiz: **{balance} so'm**" if lang == "uz" else f"💳 Ваш баланс: **{balance} сум**"
    await message.answer(bal_text, parse_mode="Markdown")

@dp.message(F.text.in_(["🔄 Yo'nalishni o'zgartirish", "🔄 Изменить маршрут"]))
async def change_route_btn(message: types.Message, state: FSMContext):
    driver_id = message.from_user.id
    if driver_id not in DRIVERS:
        return await message.answer("Siz haydovchi emassiz!")
    
    driver = DRIVERS[driver_id]
    lang = driver.get("lang", "uz")
    
    await state.set_state(BookingState.waiting_for_from_city)
    builder = ReplyKeyboardBuilder()
    for city in CITIES:
        builder.button(text=city)
    builder.adjust(2, 2, 2, 2, 2, 2)
    
    ch_text = "🔄 Yangi jo'nash shahringizni tanlang:" if lang == "uz" else "🔄 Выберите новый город отправления:"
    await message.answer(ch_text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(F.text.in_(["📋 Mos buyurtmalar", "📋 Подходящие заказы"]))
async def show_orders_btn(message: types.Message):
    driver_id = message.from_user.id
    if driver_id not in DRIVERS:
        return await message.answer("Ro'yxatdan o'tmagansiz!")

    driver = DRIVERS[driver_id]
    lang = driver.get("lang", "uz")

    if not ORDERS:
        no_ord = "Hozircha faol buyurtmalar yo'q." if lang == "uz" else "Пока нет активных заказов."
        return await message.answer(no_ord)

    found = False
    for order_id, order in ORDERS.items():
        if order['from_city'] == driver['current_city'] and order['to_city'] == driver['target_city']:
            found = True
            distance = math.sqrt((driver['lat'] - order['lat'])**2 + (driver['lon'] - order['lon'])**2) * 111
            if lang == "ru":
                indicator = "🟢 Близко" if distance <= 10 else "🔴 Далеко"
            else:
                indicator = "🟢 Yaqin" if distance <= 10 else "🔴 Uzoqroq"
            
            if lang == "uz":
                text = (
                    f"🚖 **Mos keluvchi Buyurtma #{order_id}**\n"
                    f"📍 Qayerdan: {order['from_city']}\n"
                    f"🏁 Qayerga: {order['to_city']}\n"
                    f"👥 Yo'lovchilar: {order['passengers']}\n"
                    f"💵 Narx: {order['price']}\n"
                    f"📏 Masofa: ~{round(distance, 1)} km ({indicator})"
                )
                btn_txt = "📞 Kontaktni ochish (2000 so'm)"
            else:
                text = (
                    f"🚖 **Подходящий заказ #{order_id}**\n"
                    f"📍 Откуда: {order['from_city']}\n"
                    f"🏁 Куда: {order['to_city']}\n"
                    f"👥 Пассажиры: {order['passengers']}\n"
                    f"💵 Цена: {order['price']}\n"
                    f"📏 Расстояние: ~{round(distance, 1)} км ({indicator})"
                )
                btn_txt = "📞 Открыть контакт (2000 сум)"
            
            inline_builder = InlineKeyboardBuilder()
            inline_builder.button(text=btn_txt, callback_data=f"open_contact_{order_id}")
            
            await message.answer(text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")

    if not found:
        nf_text = (
            f"Sizning yo'nalishingizga ({driver['current_city']} ➔ {driver['target_city']}) mos buyurtmalar yo'q."
            if lang == "uz" else
            f"Нет заказов по вашему маршруту ({driver['current_city']} ➔ {driver['target_city']})."
        )
        await message.answer(nf_text)

@dp.callback_query(F.data.startswith("open_contact_"))
async def open_contact_callback(callback: types.CallbackQuery):
    driver_id = callback.from_user.id
    order_id = callback.data.split("_")[2]

    if driver_id not in DRIVERS:
        return await callback.answer("Siz haydovchi emassiz!", show_alert=True)

    driver = DRIVERS[driver_id]
    lang = driver.get("lang", "uz")

    if order_id not in ORDERS:
        err_msg = "Bu buyurtma yopilgan!" if lang == "uz" else "Этот заказ закрыт!"
        return await callback.answer(err_msg, show_alert=True)

    if driver["balance"] < 2000:
        bal_msg = "Balansingiz yetarli emas!" if lang == "uz" else "Недостаточно средств!"
        return await callback.answer(bal_msg, show_alert=True)

    driver["balance"] -= 2000
    order = ORDERS[order_id]

    if lang == "uz":
        contact_text = (
            f"✅ Buyurtma ochildi!\n"
            f"👤 Yo'lovchi: {order['name']}\n"
            f"📞 Telefon: `+{order['phone']}`\n"
            f"💰 Qolgan balans: {driver['balance']} so'm"
        )
    else:
        contact_text = (
            f"✅ Заказ открыт!\n"
            f"👤 Пассажир: {order['name']}\n"
            f"📞 Телефон: `+{order['phone']}`\n"
            f"💰 Остаток баланса: {driver['balance']} сум"
        )
        
    await callback.message.answer(contact_text, parse_mode="Markdown")
    await callback.answer()

# --- YO'LOVCHI QISMI ---
@dp.message(BookingState.waiting_for_from_city)
async def select_from_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        return await cmd_start(message, state)
    
    if message.text not in CITIES:
        return await message.answer("Iltimos, tugmalardagi hududlardan birini tanlang.")

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
        return await message.answer("📍 Qayerdan jo'naysiz?", reply_markup=builder.as_markup(resize_keyboard=True))

    if message.text not in CITIES:
        return await message.answer("Iltimos, ro'yxatdagi hududlardan birini tanlang.")

    await state.update_data(to_city=message.text, passengers=[])
    await state.set_state(BookingState.waiting_for_passengers)
    await show_passenger_menu(message, [], lang)

async def show_passenger_menu(message: types.Message, passengers: list, lang: str):
    builder = ReplyKeyboardBuilder()
    if lang == "uz":
        builder.button(text="👨 Erkak")
        builder.button(text="👩 Ayol")
        builder.button(text="🔄 Tozalash")
        builder.button(text="➡️ Keyingi bo'lim")
        builder.button(text="🔙 Orqaga")
        pass_str = " ".join(passengers) if passengers else "(Hali tanlanmadi)"
        text = f"👥 Yo'lovchilar tarkibini tanlang:\nJoriy: {pass_str}"
    else:
        builder.button(text="👨 Мужчина")
        builder.button(text="👩 Женщина")
        builder.button(text="🔄 Очистить")
        builder.button(text="➡️ Следующий раздел")
        builder.button(text="🔙 Назад")
        pass_str = " ".join(passengers) if passengers else "(Еще не выбрано)"
        text = f"👥 Выберите состав пассажиров:\nТекущие: {pass_str}"
        
    builder.adjust(2, 2, 1)
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_passengers)
async def handle_passengers(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    passengers = data.get("passengers", [])
    text = message.text

    if text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_to_city)
        return await message.answer("🏁 Qayerga borasiz?")

    if text in ["🔄 Tozalash", "🔄 Очистить"]:
        passengers = []
        await state.update_data(passengers=passengers)
        return await show_passenger_menu(message, passengers, lang)

    if text in ["➡️ Keyingi bo'lim", "➡️ Следующий раздел"]:
        if not passengers:
            return await message.answer("Iltimos, kamida 1 ta yo'lovchini tanlang!")
        
        await state.set_state(BookingState.waiting_for_price)
        builder = ReplyKeyboardBuilder()
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(1)
        return await message.answer("💵 Yo'lkira uchun bermoqchi bo'lgan summangizni kiriting:", reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

    if text in ["👨 Erkak", "👨 Мужчина", "👩 Ayol", "👩 Женщина"]:
        if len(passengers) >= 4:
            return await message.answer("Maksimal 4 ta yo'lovchi!")
        emoji = "👨" if "Erkak" in text or "Мужчина" in text else "👩"
        passengers.append(emoji)
        await state.update_data(passengers=passengers)
        return await show_passenger_menu(message, passengers, lang)

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

    await message.answer("📞 Iltimos, aloqa uchun pastdagi tugmani bosing:", reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(BookingState.waiting_for_contact, F.contact)
async def get_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    phone = message.contact.phone_number
    name = message.from_user.first_name
    pass_summary = " ".join(data.get('passengers', []))

    order_id = str(len(ORDERS) + 1)
    ORDERS[order_id] = {
        "user_id": message.from_user.id,
        "name": name,
        "from_city": data.get('from_city'),
        "to_city": data.get('to_city'),
        "passengers": pass_summary,
        "price": data.get('price'),
        "phone": phone,
        "lat": 41.2995,
        "lon": 69.2401
    }

    if lang == "uz":
        response_text = (
            f"Rahmat, {name}! Buyurtmangiz qabul qilindi ✅\n\n"
            f"📋 **Buyurtma tafsilotlari:**\n"
            f"📍 Qayerdan: {data.get('from_city')}\n"
            f"🏁 Qayerga: {data.get('to_city')}\n"
            f"👥 Odamlar: {pass_summary}\n"
            f"💵 Narx: {data.get('price')}\n"
            f"📞 Tel raqam: `+{phone}`"
        )
        canc_btn = "❌ Buyurtmani bekor qilish"
    else:
        response_text = (
            f"Спасибо, {name}! Ваш заказ принят ✅\n\n"
            f"📋 **Детали заказа:**\n"
            f"📍 Откуда: {data.get('from_city')}\n"
            f"🏁 Куда: {data.get('to_city')}\n"
            f"👥 Пассажиры: {pass_summary}\n"
            f"💵 Цена: {data.get('price')}\n"
            f"📞 Телефон: `+{phone}`"
        )
        canc_btn = "❌ Отменить заказ"

    inline_builder = InlineKeyboardBuilder()
    inline_builder.button(text=canc_btn, callback_data=f"cancel_order_{order_id}")

    await message.answer(response_text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")
    await state.clear()

    order = ORDERS[order_id]
    for driver_id, driver in DRIVERS.items():
        if driver['current_city'] == order['from_city'] and driver['target_city'] == order['to_city']:
            try:
                d_lang = driver.get("lang", "uz")
                if d_lang == "uz":
                    alert_text = (
                        f"🔔 **Yangi mos buyurtma (#{order_id})**\n"
                        f"📍 Qayerdan: {order['from_city']}\n"
                        f"🏁 Qayerga: {order['to_city']}\n"
                        f"👥 Odamlar: {order['passengers']}\n"
                        f"💵 Narx: {order['price']}"
                    )
                    btn_text = "📞 Kontaktni ochish (2000 so'm)"
                else:
                    alert_text = (
                        f"🔔 **Новый подходящий заказ (#{order_id})**\n"
                        f"📍 Откуда: {order['from_city']}\n"
                        f"🏁 Куда: {order['to_city']}\n"
                        f"👥 Пассажиры: {order['passengers']}\n"
                        f"💵 Цена: {order['price']}"
                    )
                    btn_text = "📞 Открыть контакт (2000 сум)"

                drv_builder = InlineKeyboardBuilder()
                drv_builder.button(text=btn_text, callback_data=f"open_contact_{order_id}")
                await bot.send_message(driver_id, alert_text, reply_markup=drv_builder.as_markup(), parse_mode="Markdown")
            except Exception:
                pass

@dp.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order_callback(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.split("_")[2]
    if order_id in ORDERS:
        del ORDERS[order_id]

    await callback.answer("Buyurtma bekor qilindi!")
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await cmd_start(callback.message, state)

@dp.message(BookingState.waiting_for_contact)
async def wrong_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_price)
        return await message.answer("💵 Summani qaytadan kiriting:" if lang == "uz" else "💵 Введите сумму заново:")
    
    err_c = "⚠️ Iltimos, faqat pastdagi 'Kontaktni yuborish' tugmasini bosing!" if lang == "uz" else "⚠️ Пожалуйста, нажмите кнопку 'Отправить контакт' ниже!"
    await message.answer(err_c)

@dp.message()
async def echo_text(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

# --- MINI APP DIZAYNI VA HTML SAHIFA SERVERI ---
async def handle_driver_form(request):
    lang = request.query.get("lang", "uz")
    
    # O'zbek va rus tillariga moslashgan zamonaviy dizaynli Mini App formasi
    html_content = f"""
    <!DOCTYPE html>
    <html lang="{lang}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Haydovchi Anketasi</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--tg-theme-bg-color, #f4f4f9);
                color: var(--tg-theme-text-color, #222);
                margin: 0; padding: 20px;
            }}
            .card {{
                background: var(--tg-theme-secondary-bg-color, #ffffff);
                padding: 20px; border-radius: 16px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.08);
                max-width: 400px; margin: auto;
            }}
            h2 {{ text-align: center; color: var(--tg-theme-button-color, #0088cc); margin-bottom: 20px; }}
            label {{ font-size: 14px; font-weight: 600; display: block; margin-top: 12px; margin-bottom: 4px; }}
            input, select {{
                width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px;
                font-size: 15px; box-sizing: border-box; background: #fafafa;
            }}
            input:focus, select:focus {{ border-color: #0088cc; outline: none; background: #fff; }}
            button {{
                width: 100%; background-color: var(--tg-theme-button-color, #0088cc);
                color: var(--tg-theme-button-text-color, #fff); border: none;
                padding: 14px; border-radius: 10px; font-size: 16px; font-weight: bold;
                cursor: pointer; margin-top: 24px; transition: opacity 0.2s;
            }}
            button:active {{ opacity: 0.8; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🚖 {"Haydovchi Anketasi" if lang=="uz" else "Анкета Водителя"}</h2>
            <form id="driverForm">
                <label>{"Ism va Familiya:" if lang=="uz" else "Имя и Фамилия:"}</label>
                <input type="text" id="name" required placeholder="{"Masalan: Sardor Rahimov" if lang=="uz" else "Например: Сардор Рахимов"}">

                <label>{"Telefon raqam:" if lang=="uz" else "Номер телефона:"}</label>
                <input type="tel" id="phone" required placeholder="+998901234567">

                <label>{"Mashina rusumi va raqami:" if lang=="uz" else "Модель и номер машины:"}</label>
                <input type="text" id="car" required placeholder="Cobalt 01 A 777 AA">

                <label>{"Mashina rasmi (Link yoki rasm URL):" if lang=="uz" else "Фото машины (Ссылка на фото):"}</label>
                <input type="url" id="photo" placeholder="https://example.com/car.jpg">

                <label>{"Hozirgi shahar (Jo'nash):" if lang=="uz" else "Текущий город (Откуда):"}</label>
                <select id="from_city">
                    <option value="Toshkent">Toshkent</option>
                    <option value="Andijon">Andijon</option>
                    <option value="Buxoro">Buxoro</option>
                    <option value="Samarqand">Samarqand</option>
                    <option value="Namangan">Namangan</option>
                    <option value="Qarshi">Qarshi</option>
                </select>

                <label>{"Boradigan shahar:" if lang=="uz" else "Город назначения (Куда):"}</label>
                <select id="to_city">
                    <option value="Andijon">Andijon</option>
                    <option value="Toshkent">Toshkent</option>
                    <option value="Buxoro">Buxoro</option>
                    <option value="Samarqand">Samarqand</option>
                    <option value="Namangan">Namangan</option>
                    <option value="Qarshi">Qarshi</option>
                </select>

                <button type="submit">{"Ro'yxatdan o'tish" if lang=="uz" else "Зарегистрироваться"}</button>
            </form>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();

            document.getElementById('driverForm').addEventListener('submit', function(e) {
                e.preventDefault();
                let data = {
                    name: document.getElementById('name').value,
                    phone: document.getElementById('phone').value,
                    car: document.getElementById('car').value,
                    photo: document.getElementById('photo').value,
                    from_city: document.getElementById('from_city').value,
                    to_city: document.getElementById('to_city').value,
                    lang: "{lang}"
                };
                tg.sendData(JSON.stringify(data));
                tg.close();
            });
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

async def handle_home(request):
    return web.Response(text="Safar Taxi Bot va Mini App serveri ishlamoqda!")

async def web_server():
    app = web.Application()
    app.add_routes([
        web.get("/", handle_home),
        web.get("/driver-form", handle_driver_form)
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot va Mini App anketasi muvaffaqiyatli ishga tushdi...")
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.main() if hasattr(asyncio, "main") else asyncio.run(main())
