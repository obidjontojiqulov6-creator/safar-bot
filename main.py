import os
import asyncio
import logging
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
bot = Bot(token=TOKEN)
dp = Dispatcher()

ORDERS = {}       
DRIVERS = {}      
ALL_USERS = set()
DAILY_VISITS = set()
LAST_VISIT_DATE = datetime.now().date()

ADMIN_ID = 123456789  # O'zingizning Telegram ID raqamingiz

class BookingState(StatesGroup):
    waiting_for_lang = State()
    waiting_for_role = State()        
    waiting_for_from_city = State()
    waiting_for_to_city = State()
    waiting_for_passengers = State()
    waiting_for_price = State()
    waiting_for_contact = State()
    waiting_for_location = State()
    waiting_for_comment = State()

CITIES_UZ = [
    "Toshkent", "Andijon", "Buxoro", "Jizzax", 
    "Navoiy", "Namangan", "Qarshi", "Samarqand", 
    "Guliston", "Termiz", "Urganch", "Nukus"
]

CITIES_RU = [
    "Ташкент", "Андижан", "Бухара", "Джизак", 
    "Навои", "Наманган", "Карши", "Самарканд", 
    "Гулистан", "Термез", "Ургенч", "Нукус"
]

# --- START BUYRUG'I ---
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
        f"👑 **Admin paneli**\n\n"
        f"👥 Jami foydalanuvchilar: **{total_users} ta**\n"
        f"📅 Bugun kirganlar: **{today_active} ta**\n"
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
        cities = CITIES_UZ if lang == "uz" else CITIES_RU
        for city in cities:
            builder.button(text=city)
        builder.adjust(2, 2, 2, 2, 2, 2)

        city_text = "📍 Qayerdan jo'naysiz? Hududni tanlang:" if lang == "uz" else "📍 Откуда выезжаете? Выберите регион:"
        return await message.answer(city_text, reply_markup=builder.as_markup(resize_keyboard=True))

    elif text in ["🚖 Haydovchi kabineti", "🚖 Кабинет водителя"]:
        driver_id = message.from_user.id
        render_url = os.getenv("RENDER_EXTERNAL_URL", "")
        webapp_url = f"{render_url}/driver-app?lang={lang}&user_id={driver_id}"
        
        inline_builder = InlineKeyboardBuilder()
        inline_builder.button(
            text="📱 Haydovchi Mini App ochish" if lang == "uz" else "📱 Открыть Mini App водителя",
            web_app=types.WebAppInfo(url=webapp_url)
        )
        
        intro_text = (
            "🚖 **Haydovchi kabineti**\n\n"
            "Boshqaruv paneli va anketaga kirish uchun pastdagi tugmani bosing:"
            if lang == "uz" else
            "🚖 **Кабинет водителя**\n\n"
            "Нажмите на кнопку ниже, чтобы открыть панель управления и анкету:"
        )
        return await message.answer(intro_text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")

    else:
        err = "Iltimos, tugmalardan birini tanlang!" if lang == "uz" else "Пожалуйста, выберите с помощью кнопок!"
        return await message.answer(err)

@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        driver_id = message.from_user.id
        
        DRIVERS[driver_id] = {
            "name": data.get("name"),
            "profile_photo": data.get("profile_photo"),
            "phone": data.get("phone"),
            "car_model": data.get("car_model"),
            "car_plate": data.get("car_plate"),
            "car_photo1": data.get("car_photo1"),
            "car_photo2": data.get("car_photo2"),
            "from_city": data.get("from_city"),
            "to_city": data.get("to_city"),
            "passengers_count": data.get("passengers_count", 4),
            "delivery": data.get("delivery", "Yo'q"),
            "min_price": data.get("min_price", 0),
            "max_price": data.get("max_price", 0),
            "balance": data.get("balance", 10000),
            "lang": data.get("lang", "uz")
        }

        lang = data.get("lang", "uz")
        msg = "✅ Ma'lumotlaringiz muvaffaqiyatli saqlandi!" if lang == "uz" else "✅ Ваши данные успешно сохранены!"
        await message.answer(msg)
    except Exception:
        await message.answer("❌ Xatolik yuz berdi.")

# --- YO'LOVCHI SO'ROVNOMASI ---
@dp.message(BookingState.waiting_for_from_city)
async def select_from_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    cities = CITIES_UZ if lang == "uz" else CITIES_RU
    
    if message.text not in cities:
        return await message.answer("Iltimos, tugmalardagi hududlardan birini tanlang.")

    await state.update_data(from_city=message.text)
    await state.set_state(BookingState.waiting_for_to_city)

    builder = ReplyKeyboardBuilder()
    for city in cities:
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
    cities = CITIES_UZ if lang == "uz" else CITIES_RU

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_from_city)
        builder = ReplyKeyboardBuilder()
        for city in cities:
            if city != data.get("from_city"):
                builder.button(text=city)
        builder.adjust(2, 2, 2, 2, 2, 2)
        return await message.answer("📍 Qayerdan jo'naysiz?", reply_markup=builder.as_markup(resize_keyboard=True))

    if message.text not in cities:
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
        text = f"👥 Yo'lovchilar tarkibini tanlang (Maksimal: 4 ta):\nJoriy: {pass_str}"
    else:
        builder.button(text="👨 Мужчина")
        builder.button(text="👩 Женщина")
        builder.button(text="🔄 Очистить")
        builder.button(text="➡️ Следующий раздел")
        builder.button(text="🔙 Назад")
        pass_str = " ".join(passengers) if passengers else "(Еще не выбрано)"
        text = f"👥 Выберите состав пассажиров (Максимум: 4):\nТекущие: {pass_str}"
        
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
            return await message.answer("⚠️ Maksimal 4 ta yo'lovchi tanlash mumkin!")
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

    await message.answer("📞 Iltimos, aloqa uchun telefon raqamingizni yuboring:", reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(BookingState.waiting_for_contact, F.contact)
async def get_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    phone = message.contact.phone_number
    await state.update_data(phone=phone)

    await state.set_state(BookingState.waiting_for_location)
    builder = ReplyKeyboardBuilder()
    builder.button(text="📍 Jonli lokatsiyani yuborish" if lang == "uz" else "📍 Отправить живую локацию", request_location=True)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(1, 1)

    await message.answer("📍 Iltimos, turgan joyingizni **jonli lokatsiya** orqali yuboring:", reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(BookingState.waiting_for_contact)
async def wrong_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_price)
        return await message.answer("💵 Summani qaytadan kiriting:")
    await message.answer("⚠️ Iltimos, pastdagi 'Kontaktni yuborish' tugmasini bosing!")

@dp.message(BookingState.waiting_for_location, F.location)
async def get_location(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
    lat = message.location.latitude
    lon = message.location.longitude
    await state.update_data(lat=lat, lon=lon)

    await state.set_state(BookingState.waiting_for_comment)
    builder = ReplyKeyboardBuilder()
    builder.button(text="⏭️ O'tkazib yuborish" if lang == "uz" else "⏭️ Пропустить")
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(1, 1)

    await message.answer(
        "📝 Haydovchiga qo'shimcha ma'lumot yozib qoldiring. Agar yo'q bo'lsa, **'O'tkazib yuborish'** tugmasini bosing:",
        reply_markup=builder.as_markup(resize_keyboard=True),
        parse_mode="Markdown"
    )

@dp.message(BookingState.waiting_for_location)
async def wrong_location(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_contact)
        return await message.answer("📞 Telefon raqamingizni qaytadan yuboring:")
    await message.answer("⚠️ Iltimos, 'Jonli lokatsiyani yuborish' tugmasini bosing!")

@dp.message(BookingState.waiting_for_comment)
async def get_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    text = message.text

    if text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_location)
        builder = ReplyKeyboardBuilder()
        builder.button(text="📍 Jonli lokatsiyani yuborish", request_location=True)
        builder.button(text="🔙 Orqaga")
        builder.adjust(1, 1)
        return await message.answer("📍 Lokatsiyani qaytadan yuboring:", reply_markup=builder.as_markup(resize_keyboard=True))

    comment = "" if text in ["⏭️ O'tkazib yuborish", "⏭️ Пропустить"] else text
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
        "phone": data.get('phone'),
        "lat": data.get('lat'),
        "lon": data.get('lon'),
        "comment": comment if comment else ("Yo'q" if lang == "uz" else "Нет")
    }

    if lang == "uz":
        response_text = (
            f"Rahmat, {name}! Buyurtmangiz qabul qilindi ✅\n\n"
            f"📋 **Buyurtma tafsilotlari:**\n"
            f"📍 Qayerdan: {data.get('from_city')}\n"
            f"🏁 Qayerga: {data.get('to_city')}\n"
            f"👥 Odamlar: {pass_summary}\n"
            f"💵 Narx: {data.get('price')}\n"
            f"📞 Tel: `+{data.get('phone')}`\n"
            f"💬 Qo'shimcha: {ORDERS[order_id]['comment']}"
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
            f"📞 Телефон: `+{data.get('phone')}`\n"
            f"💬 Доп. инфо: {ORDERS[order_id]['comment']}"
        )
        canc_btn = "❌ Отменить заказ"

    inline_builder = InlineKeyboardBuilder()
    inline_builder.button(text=canc_btn, callback_data=f"cancel_order_{order_id}")

    await message.answer(response_text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")
    await state.clear()

@dp.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order_callback(callback: types.CallbackQuery, state: FSMContext):
    order_id = callback.data.split("_")[2]
    if order_id in ORDERS:
        del ORDERS[order_id]

    await callback.answer("Buyurtma bekor qilindi!")
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await cmd_start(callback.message, state)

@dp.message()
async def echo_text(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

# ==========================================================
# 4 BO'LIMLI MUKAMMAL HAYDOVCHI MINI APP (SERVER)
# ==========================================================
async def handle_driver_app(request):
    lang = request.query.get("lang", "uz")
    cities = CITIES_UZ if lang == "uz" else CITIES_RU
    options_html = "".join([f'<option value="{c}">{c}</option>' for c in cities])

    # Til bo'yicha matnlar
    if lang == "uz":
        t_reg = "Haydovchi Anketasi"
        l_name = "Ism va Familiya:"
        l_photo = "Profil rasmi (URL):"
        l_phone = "Telefon raqam:"
        l_car = "Avtomobil rusumi va rangi:"
        l_plate = "Avtomobil davlat raqami:"
        l_car1 = "Mashina old tomoni rasmi (URL):"
        l_car2 = "Mashina orqa tomoni rasmi (URL):"
        l_from = "Hozirgi shahar (Jo'nash):"
        l_to = "Boradigan shahar:"
        btn_reg = "Ro'yxatdan o'tish"
        t_prof = "Mening Profilim"
        lbl_name = "Ism"
        lbl_tel = "Tel"
        lbl_car_str = "Mashina"
        lbl_bal = "Balans"
        t_set = "Yo'nalish va Sozlamalar"
        l_pass_cnt = "Odamlar soni (Maksimal):"
        l_deliv = "Dastavka (Pochta/Yuk) olish:"
        l_min_p = "1 odam uchun Minimal narx (so'm):"
        l_max_p = "1 odam uchun Maksimal narx (so'm):"
        btn_save = "Saqlash"
        t_orders = "Mos keluvchi Yo'lovchilar"
        no_orders = "Hozircha buyurtmalar yo'q."
        t_topup = "Balansni to'ldirish"
        cur_bal = "Joriy balansingiz:"
        select_sum = "To'ldirish summasini tanlang:"
        nav1 = "Profil"
        nav2 = "Yo'nalish"
        nav3 = "Yo'lovchilar"
        nav4 = "Balans"
        ha = "Ha"
        yoq = "Yo'q"
    else:
        t_reg = "Анкета Водителя"
        l_name = "Имя и Фамилия:"
        l_photo = "Фото профиля (URL):"
        l_phone = "Номер телефона:"
        l_car = "Модель и цвет машины:"
        l_plate = "Гос. номер машины:"
        l_car1 = "Фото машины спереди (URL):"
        l_car2 = "Фото машины сзади (URL):"
        l_from = "Текущий город (Откуда):"
        l_to = "Город назначения (Куда):"
        btn_reg = "Зарегистрироваться"
        t_prof = "Мой Профиль"
        lbl_name = "Имя"
        lbl_tel = "Тел"
        lbl_car_str = "Машина"
        lbl_bal = "Баланс"
        t_set = "Маршрут и Настройки"
        l_pass_cnt = "Количество пассажиров (Макс):"
        l_deliv = "Доставка (Посылка/Груз):"
        l_min_p = "Минимальная цена за 1 чел (сум):"
        l_max_p = "Максимальная цена за 1 чел (сум):"
        btn_save = "Сохранить"
        t_orders = "Подходящие Пассажиры"
        no_orders = "Пока нет заказов."
        t_topup = "Пополнение баланса"
        cur_bal = "Ваш текущий баланс:"
        select_sum = "Выберите сумму пополнения:"
        nav1 = "Профиль"
        nav2 = "Маршрут"
        nav3 = "Пассажиры"
        nav4 = "Баланс"
        ha = "Да"
        yoq = "Нет"

    html_content = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{t_reg}</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--tg-theme-bg-color, #f4f4f9);
            color: var(--tg-theme-text-color, #222);
            margin: 0; padding-bottom: 70px;
        }}
        .tab-content {{ display: none; padding: 16px; }}
        .tab-content.active {{ display: block; }}
        
        .nav-bar {{
            position: fixed; bottom: 0; left: 0; width: 100%;
            background: var(--tg-theme-secondary-bg-color, #fff);
            display: flex; justify-content: space-around;
            border-top: 1px solid #ddd; padding: 8px 0;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
            box-sizing: border-box;
        }}
        .nav-item {{
            text-align: center; font-size: 11px; cursor: pointer;
            color: var(--tg-theme-hint-color, #777); font-weight: 600;
        }}
        .nav-item.active {{ color: var(--tg-theme-button-color, #0088cc); }}
        .nav-item div {{ font-size: 20px; margin-bottom: 2px; }}

        .card {{
            background: var(--tg-theme-secondary-bg-color, #ffffff);
            padding: 16px; border-radius: 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 14px;
        }}
        h2 {{ color: var(--tg-theme-button-color, #0088cc); text-align: center; margin-top: 0; }}
        label {{ font-size: 13px; font-weight: 600; display: block; margin-top: 10px; margin-bottom: 4px; }}
        input, select {{
            width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;
            font-size: 14px; box-sizing: border-box; background: var(--tg-theme-bg-color, #fafafa);
            color: var(--tg-theme-text-color, #222);
        }}
        button {{
            width: 100%; background-color: var(--tg-theme-button-color, #0088cc);
            color: var(--tg-theme-button-text-color, #fff); border: none;
            padding: 12px; border-radius: 10px; font-size: 15px; font-weight: bold;
            cursor: pointer; margin-top: 16px;
        }}
        .profile-img {{ width: 80px; height: 80px; border-radius: 50%; object-fit: cover; display: block; margin: 0 auto 10px auto; }}
        .car-photos {{ display: flex; gap: 10px; margin-top: 10px; }}
        .car-photos img {{ width: 50%; height: 90px; border-radius: 8px; object-fit: cover; }}
    </style>
</head>
<body>

    <!-- RO'YXATDAN O'TISH SAHIFASI -->
    <div id="registerScreen" class="tab-content active">
        <div class="card">
            <h2>🚖 {t_reg}</h2>
            <form id="regForm">
                <label>{l_name}</label>
                <input type="text" id="reg_name" required placeholder="Sardor Rahimov">

                <label>{l_photo}</label>
                <input type="url" id="reg_profile_photo" required placeholder="https://example.com/photo.jpg">

                <label>{l_phone}</label>
                <input type="tel" id="reg_phone" required placeholder="+998901234567">

                <label>{l_car}</label>
                <input type="text" id="reg_car_model" required placeholder="Gentra (Oq)">

                <label>{l_plate}</label>
                <input type="text" id="reg_car_plate" required placeholder="01 A 777 AA">

                <label>{l_car1}</label>
                <input type="url" id="reg_car_photo1" required placeholder="https://example.com/car1.jpg">

                <label>{l_car2}</label>
                <input type="url" id="reg_car_photo2" required placeholder="https://example.com/car2.jpg">

                <label>{l_from}</label>
                <select id="reg_from">{options_html}</select>

                <label>{l_to}</label>
                <select id="reg_to">{options_html}</select>

                <button type="submit">{btn_reg}</button>
            </form>
        </div>
    </div>

    <!-- DASHBOARD -->
    <div id="dashboardApp" style="display: none;">
        
        <!-- 1-BO'LIM: PROFIL -->
        <div id="tab1" class="tab-content">
            <div class="card">
                <h2>👤 {t_prof}</h2>
                <img id="p_img" class="profile-img" src="" alt="Profil">
                <p><b>👤 {lbl_name}:</b> <span id="p_name"></span></p>
                <p><b>📞 {lbl_tel}:</b> <span id="p_phone"></span></p>
                <p><b>🚗 {lbl_car_str}:</b> <span id="p_car"></span> (<span id="p_plate"></span>)</p>
                <p><b>💳 {lbl_bal}:</b> <span id="p_balance"></span> so'm</p>
                <div class="car-photos">
                    <img id="p_car1" src="" alt="Car 1">
                    <img id="p_car2" src="" alt="Car 2">
                </div>
            </div>
        </div>

        <!-- 2-BO'LIM: YO'NALISH -->
        <div id="tab2" class="tab-content">
            <div class="card">
                <h2>⚙️ {t_set}</h2>
                <form id="settingsForm">
                    <label>{l_from}</label>
                    <select id="set_from">{options_html}</select>

                    <label>{l_to}</label>
                    <select id="set_to">{options_html}</select>

                    <label>{l_pass_cnt}</label>
                    <select id="set_passengers">
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="4" selected>4</option>
                    </select>

                    <label>{l_deliv}</label>
                    <select id="set_delivery">
                        <option value="{ha}">{ha}</option>
                        <option value="{yoq}" selected>{yoq}</option>
                    </select>

                    <label>{l_min_p}</label>
                    <input type="number" id="set_min_price" value="50000">

                    <label>{l_max_p}</label>
                    <input type="number" id="set_max_price" value="150000">

                    <button type="submit">{btn_save}</button>
                </form>
            </div>
        </div>

        <!-- 3-BO'LIM: YO'LOVCHILAR -->
        <div id="tab3" class="tab-content">
            <div class="card">
                <h2>👥 {t_orders}</h2>
                <div id="ordersList">
                    <p style="text-align: center; color: #777;">{no_orders}</p>
                </div>
            </div>
        </div>

        <!-- 4-BO'LIM: BALANS -->
        <div id="tab4" class="tab-content">
            <div class="card">
                <h2>💳 {t_topup}</h2>
                <p>{cur_bal} <b id="b_balance" style="color: green;">0</b> so'm</p>
                <label>{select_sum}</label>
                <div style="display: flex; gap: 10px; margin-top: 10px;">
                    <button type="button" onclick="topUp(10000)">+ 10,000</button>
                    <button type="button" onclick="topUp(25000)">+ 25,000</button>
                    <button type="button" onclick="topUp(50000)">+ 50,000</button>
                </div>
            </div>
        </div>

        <!-- NAVBAR -->
        <div class="nav-bar">
            <div class="nav-item active" onclick="switchTab(1)">
                <div>👤</div>{nav1}
            </div>
            <div class="nav-item" onclick="switchTab(2)">
                <div>⚙️</div>{nav2}
            </div>
            <div class="nav-item" onclick="switchTab(3)">
                <div>👥</div>{nav3}
            </div>
            <div class="nav-item" onclick="switchTab(4)">
                <div>💳</div>{nav4}
            </div>
        </div>

    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();

        let driverData = localStorage.getItem('safar_driver');

        if (driverData) {{
            showDashboard(JSON.parse(driverData));
        }}

        document.getElementById('regForm').addEventListener('submit', function(e) {{
            e.preventDefault();
            let data = {{
                name: document.getElementById('reg_name').value,
                profile_photo: document.getElementById('reg_profile_photo').value,
                phone: document.getElementById('reg_phone').value,
                car_model: document.getElementById('reg_car_model').value,
                car_plate: document.getElementById('reg_car_plate').value,
                car_photo1: document.getElementById('reg_car_photo1').value,
                car_photo2: document.getElementById('reg_car_photo2').value,
                from_city: document.getElementById('reg_from').value,
                to_city: document.getElementById('reg_to').value,
                passengers_count: 4,
                delivery: "{yoq}",
                min_price: 50000,
                max_price: 150000,
                balance: 15000,
                lang: "{lang}"
            }};

            localStorage.setItem('safar_driver', JSON.stringify(data));
            tg.sendData(JSON.stringify(data));
            showDashboard(data);
        }});

        document.getElementById('settingsForm').addEventListener('submit', function(e) {{
            e.preventDefault();
            let data = JSON.parse(localStorage.getItem('safar_driver'));
            data.from_city = document.getElementById('set_from').value;
            data.to_city = document.getElementById('set_to').value;
            data.passengers_count = document.getElementById('set_passengers').value;
            data.delivery = document.getElementById('set_delivery').value;
            data.min_price = document.getElementById('set_min_price').value;
            data.max_price = document.getElementById('set_max_price').value;

            localStorage.setItem('safar_driver', JSON.stringify(data));
            tg.sendData(JSON.stringify(data));
            alert("Saqlandi!");
        }});

        function showDashboard(data) {{
            document.getElementById('registerScreen').style.display = 'none';
            document.getElementById('dashboardApp').style.display = 'block';

            document.getElementById('p_img').src = data.profile_photo;
            document.getElementById('p_name').innerText = data.name;
            document.getElementById('p_phone').innerText = data.phone;
            document.getElementById('p_car').innerText = data.car_model;
            document.getElementById('p_plate').innerText = data.car_plate;
            document.getElementById('p_balance').innerText = data.balance;
            document.getElementById('b_balance').innerText = data.balance;
            document.getElementById('p_car1').src = data.car_photo1;
            document.getElementById('p_car2').src = data.car_photo2;

            document.getElementById('set_from').value = data.from_city;
            document.getElementById('set_to').value = data.to_city;
            document.getElementById('set_passengers').value = data.passengers_count;
            document.getElementById('set_delivery').value = data.delivery;
            document.getElementById('set_min_price').value = data.min_price;
            document.getElementById('set_max_price').value = data.max_price;
        }}

        function switchTab(tabNum) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

            if(tabNum === 1) document.getElementById('tab1').classList.add('active');
            if(tabNum === 2) document.getElementById('tab2').classList.add('active');
            if(tabNum === 3) document.getElementById('tab3').classList.add('active');
            if(tabNum === 4) document.getElementById('tab4').classList.add('active');

            document.querySelectorAll('.nav-item')[tabNum - 1].classList.add('active');
        }}

        function topUp(amount) {{
            let data = JSON.parse(localStorage.getItem('safar_driver'));
            data.balance += amount;
            localStorage.setItem('safar_driver', JSON.stringify(data));
            document.getElementById('p_balance').innerText = data.balance;
            document.getElementById('b_balance').innerText = data.balance;
            alert("Balans to'ldirildi!");
        }}
    </script>
</body>
</html>
"""
    return web.Response(text=html_content, content_type='text/html')

async def handle_home(request):
    return web.Response(text="Safar Taxi Bot va Mini App ishlamoqda!")

async def web_server():
    app = web.Application()
    app.add_routes([
        web.get("/", handle_home),
        web.get("/driver-app", handle_driver_app)
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot va Mukammal Haydovchi Mini App ishga tushdi...")
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
