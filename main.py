import os
import asyncio
import logging
import math
import aiohttp
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

class DriverState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_car = State()
    waiting_for_photo = State()
    waiting_for_current_city = State()
    waiting_for_target_city = State()
    waiting_for_location = State()

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

    # Yo'lovchi tanlansa
    if text in ["👤 Yo'lovchi", "👤 Пассажир"]:
        await state.set_state(BookingState.waiting_for_from_city)
        builder = ReplyKeyboardBuilder()
        for city in CITIES:
            builder.button(text=city)
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(2, 2, 2, 2, 2, 2, 1)

        city_text = "📍 Qayerdan jo'naysiz? Hududni tanlang:" if lang == "uz" else "📍 Откуда выезжаете? Выберите регион:"
        return await message.answer(city_text, reply_markup=builder.as_markup(resize_keyboard=True))

    # Haydovchi tanlansa (W-Coin uslubidagi maxsus tugma va panel)
    elif text in ["🚖 Haydovchi kabineti", "🚖 Кабинет водителя"]:
        driver_id = message.from_user.id
        if driver_id not in DRIVERS:
            await state.update_data(lang=lang)
            await state.set_state(DriverState.waiting_for_name)
            
            # W-Coin kabi ochiladigan chiroyli Inline tugma yasaymiz
            inline_builder = InlineKeyboardBuilder()
            # Hozircha bu yerga namunaviy mini-app yoki to'g'ridan to'g'ri ro'yxatni boshlash tugmasini qo'yamiz
            inline_builder.button(text="🚗 Haydovchi panellarini ochish", callback_data="open_driver_reg")
            
            intro_text = (
                "🚖 **Haydovchilar bo'limiga xush kelibsiz!**\n"
                "Ro'yxatdan o'tishni boshlash uchun pastdagi tugmani bosing:"
                if lang == "uz" else
                "🚖 **Добро пожаловать в кабинет водителя!**\n"
                "Нажмите кнопку ниже, чтобы начать регистрацию:"
            )
            return await message.answer(intro_text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")
        else:
            DRIVERS[driver_id]["lang"] = lang
            return await show_driver_menu(message)
    
    else:
        err = "Iltimos, tugmalardan birini tanlang!" if lang == "uz" else "Пожалуйста, выберите с помощью кнопок!"
        return await message.answer(err)

# --- HAYDOVCHI RO'YXATDAN O'TISH JARAYONI (W-COIN USLUBIDAGI ANKETA) ---
@dp.callback_query(F.data == "open_driver_reg")
async def start_driver_registration(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    await state.set_state(DriverState.waiting_for_name)
    
    text = (
        "📝 **Haydovchini ro'yxatdan o'tkazish**\n\n"
        "1️⃣ Iltimos, **Ism va Familiyangizni** kiriting (Masalan: *Sardorbek Rahimov*):"
        if lang == "uz" else
        "📝 **Регистрация водителя**\n\n"
        "1️⃣ Пожалуйста, введите ваше **Имя и Фамилию** (Например: *Сардор Рахимов*):"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.message(DriverState.waiting_for_name)
async def driver_get_name(message: types.Message, state: FSMContext):
    await state.update_data(driver_name=message.text)
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    await state.set_state(DriverState.waiting_for_phone)
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Telefon raqamni yuborish" if lang == "uz" else "📱 Отправить номер", request_contact=True)
    
    text = (
        "2️⃣ Telefon raqamingizni yuboring (Pastdagi tugmani bosing):"
        if lang == "uz" else
        "2️⃣ Отправьте ваш номер телефона (нажмите кнопку ниже):"
    )
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(DriverState.waiting_for_phone, F.contact)
async def driver_get_phone(message: types.Message, state: FSMContext):
    await state.update_data(driver_phone=message.contact.phone_number)
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    await state.set_state(DriverState.waiting_for_car)
    
    text = (
        "3️⃣ Mashinangiz rusumi va raqamini kiriting (Masalan: `Cobalt 01 A 777 AA`):"
        if lang == "uz" else
        "3️⃣ Введите модель и номер машины (Например: `Cobalt 01 A 777 AA`):"
    )
    await message.answer(text, reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message(DriverState.waiting_for_car)
async def driver_get_car(message: types.Message, state: FSMContext):
    await state.update_data(car=message.text)
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    await state.set_state(DriverState.waiting_for_photo)
    
    text = (
        "4️⃣ Mashinangizning **rasmini** yuboring:"
        if lang == "uz" else
        "4️⃣ Отправьте **фотографию** вашей машины:"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(DriverState.waiting_for_photo, F.photo)
async def driver_get_photo(message: types.Message, state: FSMContext):
    # Rasmning file_id sini saqlab qolamiz
    photo_id = message.photo[-1].file_id
    await state.update_data(car_photo=photo_id)
    
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    await state.set_state(DriverState.waiting_for_current_city)
    
    builder = ReplyKeyboardBuilder()
    for city in CITIES:
        builder.button(text=city)
    builder.adjust(2, 2, 2, 2, 2, 2)
    
    text = (
        "5️⃣ Hozir qaysi shahardasiz? (Jo'nash punkti):"
        if lang == "uz" else
        "5️⃣ В каком городе вы сейчас? (Откуда выезжаете):"
    )
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(DriverState.waiting_for_current_city)
async def driver_get_current_city(message: types.Message, state: FSMContext):
    if message.text not in CITIES:
        return await message.answer("Iltimos, tugmalardagi shaharlardan birini tanlang.")
    
    await state.update_data(current_city=message.text)
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    await state.set_state(DriverState.waiting_for_target_city)

    builder = ReplyKeyboardBuilder()
    for city in CITIES:
        if city != message.text:
            builder.button(text=city)
    builder.adjust(2, 2, 2, 2, 2, 2)

    text = f"6️⃣ Qaysi shaharga borasiz? (Hozirgi: {message.text}):" if lang == "uz" else f"6️⃣ Куда едете? (Текущий: {message.text}):"
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(DriverState.waiting_for_target_city)
async def driver_get_target_city(message: types.Message, state: FSMContext):
    if message.text not in CITIES:
        return await message.answer("Iltimos, tugmalardagi shaharlardan birini tanlang.")

    await state.update_data(target_city=message.text)
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    await state.set_state(DriverState.waiting_for_location)

    builder = ReplyKeyboardBuilder()
    builder.button(text="📍 Lokatsiyani yuborish" if lang == "uz" else "📍 Отправить локацию", request_location=True)
    builder.adjust(1)

    text = "7️⃣ Oxirgi qadam: Aniq masofani hisoblash uchun turgan joyingizni (lokatsiyangizni) yuboring:" if lang == "uz" else "7️⃣ Последний шаг: Отправьте вашу текущую локацию:"
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(DriverState.waiting_for_location, F.location)
async def driver_get_location(message: types.Message, state: FSMContext):
    data = await state.get_data()
    driver_id = message.from_user.id
    lang = data.get("lang", "uz")
    
    DRIVERS[driver_id] = {
        "name": data.get("driver_name"),
        "phone": data.get("driver_phone"),
        "car": data.get("car"),
        "photo": data.get("car_photo"),
        "current_city": data.get("current_city"),
        "target_city": data.get("target_city"),
        "lat": message.location.latitude,
        "lon": message.location.longitude,
        "balance": 10000,
        "lang": lang
    }

    success_text = "✅ Ro'yxatdan o'tish muvaffaqiyatli yakunlandi!" if lang == "uz" else "✅ Регистрация успешно завершена!"
    await message.answer(success_text)
    await state.clear()
    await show_driver_menu(message)

# --- HAYDOVCHI MENYUSI ---
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
    else:
        builder.button(text="📋 Подходящие заказы")
        builder.button(text="🔄 Изменить маршрут")
        builder.button(text="💰 Проверить баланс")
        builder.button(text="📍 Обновить локацию", request_location=True)
        builder.button(text="🏠 Главное меню")
        
    builder.adjust(2, 1, 1, 1)

    text = (
        f"🚖 **Haydovchi kabineti**\n\n"
        f"👤 Ism: {driver['name']}\n"
        f"📞 Tel: `+{driver['phone']}`\n"
        f"🚗 Mashina: {driver['car']}\n"
        f"📍 Turgan joyi: **{driver['current_city']}** ➔ Boradigan joyi: **{driver['target_city']}**\n"
        f"💳 Balans: {driver['balance']} so'm"
        if lang == "uz" else
        f"🚖 **Кабинет водителя**\n\n"
        f"👤 Имя: {driver['name']}\n"
        f"📞 Тел: `+{driver['phone']}`\n"
        f"🚗 Машина: {driver['car']}\n"
        f"📍 Откуда: **{driver['current_city']}** ➔ Куда: **{driver['target_city']}**\n"
        f"💳 Баланс: {driver['balance']} сум"
    )
    
    # Agar mashina rasmi bo'lsa, rasmni biriktirib yuboramiz
    if driver.get("photo"):
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
    
    await state.set_state(DriverState.waiting_for_current_city)
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
    print("Bot haydovchi anketa paneli bilan ishga tushdi...")
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.main() if hasattr(asyncio, "main") else asyncio.run(main())
