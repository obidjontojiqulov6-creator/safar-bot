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

ORDERS = {
    "1": {
        "id": "1",
        "name": "Ali Valiyev",
        "from_city": "Toshkent",
        "to_city": "Buxoro",
        "passengers": "👨 👨",
        "price": "70000",
        "phone": "998901234567",
        "type": "🚖 Yo'lovchi",
        "comment": "Sumka bor"
    },
    "2": {
        "id": "2",
        "name": "Sardor",
        "from_city": "Toshkent",
        "to_city": "Samarqand",
        "passengers": "Og'irlik: 10 kg",
        "price": "50000",
        "phone": "998919876543",
        "type": "📦 Dastafka",
        "comment": "Kichik quti (hujjatlar)"
    }
}

ALL_USERS = set()
DAILY_VISITS = set()
LAST_VISIT_DATE = datetime.now().date()
ADMIN_ID = 123456789

class BookingState(StatesGroup):
    waiting_for_lang = State()
    waiting_for_role = State()        
    waiting_for_from_city = State()
    waiting_for_to_city = State()
    waiting_for_passengers = State()
    waiting_for_weight = State()      
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

@dp.message(BookingState.waiting_for_lang, F.text.in_(["🇺🇿 O'zbekcha", "🇷🇺 Русский"]))
async def select_language(message: types.Message, state: FSMContext):
    lang = "uz" if "O'zbekcha" in message.text else "ru"
    await state.update_data(lang=lang)
    await state.set_state(BookingState.waiting_for_role)

    builder = ReplyKeyboardBuilder()
    if lang == "uz":
        builder.button(text="👤 Yo'lovchi")
        builder.button(text="📦 Dastafka yuboruvchi")
        builder.button(text="🚖 Haydovchi kabineti")
        text = "Siz kimsiz? Iltimos, o'z rolingizni tanlang:"
    else:
        builder.button(text="👤 Пассажир")
        builder.button(text="📦 Отправитель доставки")
        builder.button(text="🚖 Кабинет водителя")
        text = "Кто вы? Пожалуйста, выберите свою роль:"
    
    builder.adjust(1, 2)
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_role)
async def select_role(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    text = message.text

    if text in ["👤 Yo'lovchi", "👤 Пассажир"]:
        await state.update_data(order_type="passenger")
        await state.set_state(BookingState.waiting_for_from_city)
        return await ask_from_city(message, lang, "passenger")

    elif text in ["📦 Dastafka yuboruvchi", "📦 Отправитель доставки"]:
        await state.update_data(order_type="delivery")
        await state.set_state(BookingState.waiting_for_from_city)
        return await ask_from_city(message, lang, "delivery")

    elif text in ["🚖 Haydovchi kabineti", "🚖 Кабинет водителя"]:
        driver_id = message.from_user.id
        render_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip('/')
        if not render_url:
            render_url = "https://safar-taxi.onrender.com"
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

async def ask_from_city(message: types.Message, lang: str, order_type: str):
    builder = ReplyKeyboardBuilder()
    cities = CITIES_UZ if lang == "uz" else CITIES_RU
    for city in cities:
        builder.button(text=city)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(2, 2, 2, 2, 2, 2, 1)
    
    if order_type == "passenger":
        city_text = "📍 Qayerdan yo'lga chiqasiz? Hududni tanlang:" if lang == "uz" else "📍 Откуда выезжаете? Выберите регион:"
    else:
        city_text = "📍 Qayerdan jo'natasiz? Hududni tanlang:" if lang == "uz" else "📍 Откуда отправляете? Выберите регион:"
        
    await message.answer(city_text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_from_city)
async def select_from_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    order_type = data.get("order_type", "passenger")
    cities = CITIES_UZ if lang == "uz" else CITIES_RU

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_role)
        builder = ReplyKeyboardBuilder()
        if lang == "uz":
            builder.button(text="👤 Yo'lovchi")
            builder.button(text="📦 Dastafka yuboruvchi")
            builder.button(text="🚖 Haydovchi kabineti")
            text = "Siz kimsiz? Iltimos, o'z rolingizni tanlang:"
        else:
            builder.button(text="👤 Пассажир")
            builder.button(text="📦 Отправитель доставки")
            builder.button(text="🚖 Кабинет водителя")
            text = "Кто вы? Пожалуйста, выберите свою роль:"
        builder.adjust(1, 2)
        return await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))
    
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

    if order_type == "passenger":
        text = f"🏁 Qayerga borasiz? (Jo'nash: {message.text})" if lang == "uz" else f"🏁 Куда едете? (Откуда: {message.text})"
    else:
        text = f"🏁 Qayerga jo'natasiz? (Jo'natish: {message.text})" if lang == "uz" else f"🏁 Куда отправляете? (Откуда: {message.text})"
        
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_to_city)
async def select_to_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    order_type = data.get("order_type", "passenger")
    cities = CITIES_UZ if lang == "uz" else CITIES_RU

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_from_city)
        return await ask_from_city(message, lang, order_type)

    if message.text not in cities:
        return await message.answer("Iltimos, ro'yxatdagi hududlardan birini tanlang.")

    await state.update_data(to_city=message.text)
    
    if order_type == "passenger":
        await state.update_data(passengers=[])
        await state.set_state(BookingState.waiting_for_passengers)
        await show_passenger_menu(message, [], lang)
    else:
        await state.set_state(BookingState.waiting_for_weight)
        builder = ReplyKeyboardBuilder()
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(1)
        await message.answer("⚖️ Yukning taxminiy og'irligini kiriting (masalan: 5 kg, 20 kg):" if lang == "uz" else "⚖️ Введите примерный вес груза (например: 5 кг):", reply_markup=builder.as_markup(resize_keyboard=True))

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
        cities = CITIES_UZ if lang == "uz" else CITIES_RU
        from_city = data.get('from_city')
        builder = ReplyKeyboardBuilder()
        for city in cities:
            if city != from_city:
                builder.button(text=city)
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(2, 2, 2, 2, 2, 2, 1)
        return await message.answer(f"🏁 Qayerga borasiz? (Jo'nash: {from_city})", reply_markup=builder.as_markup(resize_keyboard=True))

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
        return await message.answer("💵 Yo'lkira uchun bermoqchi bo'lgan summangizni kiriting:", reply_markup=builder.as_markup(resize_keyboard=True))

    if text in ["👨 Erkak", "👨 Мужчина", "👩 Ayol", "👩 Женщина"]:
        if len(passengers) >= 4:
            return await message.answer("⚠️ Maksimal 4 ta yo'lovchi tanlash mumkin!")
        emoji = "👨" if "Erkak" in text or "Мужчина" in text else "👩"
        passengers.append(emoji)
        await state.update_data(passengers=passengers)
        return await show_passenger_menu(message, passengers, lang)

@dp.message(BookingState.waiting_for_weight)
async def get_weight(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_to_city)
        cities = CITIES_UZ if lang == "uz" else CITIES_RU
        from_city = data.get('from_city')
        builder = ReplyKeyboardBuilder()
        for city in cities:
            if city != from_city:
                builder.button(text=city)
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(2, 2, 2, 2, 2, 2, 1)
        return await message.answer(f"🏁 Qayerga jo'natasiz? (Jo'natish: {from_city})", reply_markup=builder.as_markup(resize_keyboard=True))

    if not message.text:
        return await message.answer("⚠️ Iltimos, og'irlikni matn ko'rinishida kiriting!")

    await state.update_data(weight=message.text)
    await state.set_state(BookingState.waiting_for_price)

    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(1)
    await message.answer("💵 Yukni yetkazib berish uchun bermoqchi bo'lgan pulingizni (haqini) kiriting:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_price, F.text)
async def enter_price_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    order_type = data.get("order_type", "passenger")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        if order_type == "passenger":
            await state.set_state(BookingState.waiting_for_passengers)
            return await show_passenger_menu(message, data.get("passengers", []), lang)
        else:
            await state.set_state(BookingState.waiting_for_weight)
            builder = ReplyKeyboardBuilder()
            builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
            builder.adjust(1)
            return await message.answer("⚖️ Yuk og'irligini qaytadan kiriting:", reply_markup=builder.as_markup(resize_keyboard=True))

    await state.update_data(price=message.text)
    await state.set_state(BookingState.waiting_for_contact)

    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Kontaktni yuborish" if lang == "uz" else "📱 Отправить контакт", request_contact=True)
    builder.adjust(1)

    await message.answer("📞 Aloqa uchun telefon raqamingizni yuboring:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_price)
async def enter_price_invalid(message: types.Message, state: FSMContext):
    await message.answer("⚠️ Iltimos, summani matn/raqamlarda kiriting!")

@dp.message(BookingState.waiting_for_contact, F.contact)
async def get_contact_obj(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await ask_location_step(message, state)

@dp.message(BookingState.waiting_for_contact)
async def wrong_contact(message: types.Message, state: FSMContext):
    await message.answer("⚠️ Iltimos, pastdagi '📱 Kontaktni yuborish' tugmasini bosing!")

async def ask_location_step(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    await state.set_state(BookingState.waiting_for_location)
    builder = ReplyKeyboardBuilder()
    builder.button(text="📍 Joylashuvni tanlash va yuborish", request_location=True)
    builder.adjust(1)

    text = (
        "📍 Turgan joyingizni belgilang:\n\n"
        "Pastdagi **'📍 Joylashuvni tanlash va yuborish'** tugmasini bosing. "
        "Ochilgan xaritadan o'zingiz turgan joyni aniq tanlab yuboring!"
        if lang == "uz" else
        "📍 Укажите ваше местоположение:\n\n"
        "Нажмите кнопку **'📍 Выбрать и отправить локацию'** ниже. "
        "Укажите точное место на карте!"
    )

    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(BookingState.waiting_for_location, F.location)
async def get_location_obj(message: types.Message, state: FSMContext):
    lat = message.location.latitude
    lon = message.location.longitude
    await state.update_data(lat=lat, lon=lon)
    await ask_comment_step(message, state)

@dp.message(BookingState.waiting_for_location)
async def wrong_location(message: types.Message, state: FSMContext):
    await message.answer("⚠️ Iltimos, pastdagi '📍 Joylashuvni tanlash va yuborish' tugmasini bosing!")

async def ask_comment_step(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    await state.set_state(BookingState.waiting_for_comment)
    builder = ReplyKeyboardBuilder()
    builder.button(text="⏭️ O'tkazib yuborish" if lang == "uz" else "⏭️ Пропустить")
    builder.adjust(1)

    await message.answer("📝 Qo'shimcha izoh yozib qoldiring:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_comment)
async def get_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    text = message.text if message.text else ""

    comment = "" if text in ["⏭️ O'tkazib yuborish", "⏭️ Пропустить"] else text
    name = message.from_user.first_name
    order_type = data.get("order_type", "passenger")

    order_id = str(len(ORDERS) + 1)
    if order_type == "passenger":
        pass_summary = " ".join(data.get('passengers', []))
        o_type_str = "🚖 Yo'lovchi"
    else:
        weight_val = data.get('weight', 'Korsatilmagan')
        pass_summary = f"Og'irlik: {weight_val}"
        o_type_str = "📦 Dastafka"

    phone_val = data.get('phone', 'Kiritilmadi')

    ORDERS[order_id] = {
        "id": order_id,
        "user_id": message.from_user.id,
        "name": name,
        "from_city": data.get('from_city'),
        "to_city": data.get('to_city'),
        "passengers": pass_summary,
        "price": data.get('price'),
        "phone": phone_val,
        "lat": data.get('lat'),
        "lon": data.get('lon'),
        "type": o_type_str,
        "comment": comment if comment else "Yo'q"
    }

    response_text = (
        f"Rahmat, {name}! Buyurtmangiz qabul qilindi ✅\n\n"
        f"📋 **Buyurtma tafsilotlari:**\n"
        f"🔹 Turi: {o_type_str}\n"
        f"📍 Qayerdan: {data.get('from_city')}\n"
        f"🏁 Qayerga: {data.get('to_city')}\n"
        f"📌 Ma'lumot: {pass_summary}\n"
        f"💵 Taklif narx: {data.get('price')} so'm\n"
        f"📞 Tel: `+{phone_val}`"
    )

    inline_builder = InlineKeyboardBuilder()
    inline_builder.button(text="❌ Buyurtmani bekor qilish", callback_data=f"cancel_order_{order_id}")

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

async def handle_get_orders(request):
    return web.json_response(list(ORDERS.values()))

async def handle_driver_app(request):
    lang = request.query.get("lang", "uz")
    cities = CITIES_UZ if lang == "uz" else CITIES_RU
    options_html = "".join([f'<option value="{c}">{c}</option>' for c in cities])

    html_template = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Safar Driver</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --bg-color: #0f1015;
            --card-bg: #181a20;
            --text-color: #ffffff;
            --text-secondary: #9ca3af;
            --accent-color: #f59e0b;
            --accent-gradient: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            --border-color: #262830;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0; padding: 12px; padding-bottom: 80px;
        }
        .screen-block { display: none; }
        .screen-block.active { display: block !important; }

        .header-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 16px; border-radius: 16px;
            display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 16px;
        }
        .driver-info h3 { margin: 0; font-size: 16px; color: var(--text-color); }
        .driver-info p { margin: 4px 0 0 0; font-size: 12px; color: var(--text-secondary); }
        .balance-badge {
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-color);
            padding: 6px 12px; border-radius: 20px;
            font-weight: 700; font-size: 13px;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 16px; border-radius: 16px;
            margin-bottom: 14px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        h2 { color: var(--accent-color); font-size: 18px; margin-top: 0; margin-bottom: 12px; text-align: center; }
        label { font-size: 12px; font-weight: 600; display: block; margin-top: 10px; margin-bottom: 4px; color: var(--text-secondary); }
        
        input, select {
            width: 100%; padding: 12px; border: 1px solid var(--border-color); border-radius: 10px;
            font-size: 14px; box-sizing: border-box; background: #21242d;
            color: var(--text-color); outline: none;
        }
        input:focus, select:focus { border-color: var(--accent-color); }

        button.btn-primary {
            width: 100%; background: var(--accent-gradient);
            color: #000000; border: none;
            padding: 14px; border-radius: 12px; font-size: 15px; font-weight: 800;
            cursor: pointer; margin-top: 16px;
            box-shadow: 0 4px 15px rgba(245, 158, 11, 0.3);
        }
        .reset-btn { background: #ef4444 !important; color: #fff !important; margin-top: 20px; }

        .order-card {
            background: #21242d;
            border: 1px solid var(--border-color);
            border-left: 4px solid var(--accent-color);
            padding: 14px; border-radius: 12px;
            margin-bottom: 12px;
        }
        .order-title { font-weight: bold; font-size: 15px; margin-bottom: 6px; display: flex; justify-content: space-between; }
        .order-info { font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; }
        .buy-btn {
            background: #10b981; color: #fff; padding: 10px; font-size: 13px;
            margin-top: 10px; border-radius: 8px; border: none; width: 100%; font-weight: bold; cursor: pointer;
        }

        .nav-bar {
            position: fixed; bottom: 0; left: 0; width: 100%;
            background: #12141c;
            display: flex; justify-content: space-around;
            border-top: 1px solid var(--border-color); padding: 10px 0;
            box-sizing: border-box; z-index: 999;
        }
        .nav-item {
            text-align: center; font-size: 11px; cursor: pointer;
            color: var(--text-secondary); font-weight: 600;
        }
        .nav-item.active { color: var(--accent-color); }
        .nav-item div { font-size: 20px; margin-bottom: 2px; }
    </style>
</head>
<body>

    <!-- RO'YXATDAN O'TISH ERKAN -->
    <div id="registerScreen" class="screen-block active">
        <div class="card">
            <h2>🚖 Haydovchi Anketasi</h2>
            <label>Ism va Familiya:</label>
            <input type="text" id="reg_name" placeholder="Sardor Rahimov">

            <label>Telefon raqam:</label>
            <input type="tel" id="reg_phone" placeholder="+998901234567">

            <label>Avtomobil rusumi va rangi:</label>
            <input type="text" id="reg_car_model" placeholder="Gentra (Oq)">

            <label>Avtomobil davlat raqami:</label>
            <input type="text" id="reg_car_plate" placeholder="01 A 777 AA">

            <button type="button" class="btn-primary" onclick="submitRegistration()">Ro'yxatdan o'tish</button>
        </div>
    </div>

    <!-- ASOSIY DASHBOARD APP -->
    <div id="dashboardApp" style="display: none;">
        
        <div class="header-card">
            <div class="driver-info">
                <h3 id="h_name">Haydovchi</h3>
                <p id="h_car">Mashina ma'lumoti</p>
            </div>
            <div class="balance-badge"><span id="p_balance">15000</span> so'm</div>
        </div>

        <!-- TAB 1: PROFIL -->
        <div id="tab1" class="screen-block active">
            <div class="card">
                <h2>👤 Mening Profilim</h2>
                <p><b>📞 Tel:</b> <span id="p_phone"></span></p>
                <p><b>🚗 Mashina:</b> <span id="p_car"></span> (<span id="p_plate"></span>)</p>
                <button type="button" class="btn-primary reset-btn" onclick="clearData()">🔄 Qaytadan ro'yxatdan o'tish</button>
            </div>
        </div>

        <!-- TAB 2: YO'NALISH -->
        <div id="tab2" class="screen-block">
            <div class="card">
                <h2>⚙️ Yo'nalish sozlamalari</h2>
                <label>Jo'nash shahri:</label>
                <select id="set_from">{{OPTIONS_HTML}}</select>

                <label>Boradigan shahar:</label>
                <select id="set_to">{{OPTIONS_HTML}}</select>

                <label>1 odam uchun narx (so'm):</label>
                <input type="number" id="set_min_price" value="50000">

                <button type="button" class="btn-primary" onclick="alert('Sozlamalar saqlandi!')">Saqlash</button>
            </div>
        </div>

        <!-- TAB 3: BUYURTMALAR -->
        <div id="tab3" class="screen-block">
            <div class="card">
                <h2>👥 Mos Buyurtmalar</h2>
                <div id="ordersList">
                    <p style="text-align: center; color: #777;">Yuklanmoqda...</p>
                </div>
            </div>
        </div>

        <!-- TAB 4: BALANS -->
        <div id="tab4" class="screen-block">
            <div class="card">
                <h2>💳 Balansni to'ldirish</h2>
                <p>Joriy balans: <b id="b_balance" style="color: var(--accent-color);">0</b> so'm</p>
                <label>Summani tanlang:</label>
                <div style="display: flex; gap: 10px; margin-top: 10px;">
                    <button type="button" class="btn-primary" onclick="topUp(10000)">+ 10,000</button>
                    <button type="button" class="btn-primary" onclick="topUp(25000)">+ 25,000</button>
                    <button type="button" class="btn-primary" onclick="topUp(50000)">+ 50,000</button>
                </div>
            </div>
        </div>

        <!-- BOTTOM NAVBAR -->
        <div class="nav-bar">
            <div class="nav-item active" onclick="switchTab(1)">
                <div>👤</div>Profil
            </div>
            <div class="nav-item" onclick="switchTab(2)">
                <div>⚙️</div>Yo'nalish
            </div>
            <div class="nav-item" onclick="switchTab(3)">
                <div>👥</div>Buyurtmalar
            </div>
            <div class="nav-item" onclick="switchTab(4)">
                <div>💳</div>Balans
            </div>
        </div>
    </div>

    <script>
        let tg = window.Telegram ? window.Telegram.WebApp : null;
        if(tg) { try { tg.expand(); } catch(e) {} }

        let openedOrders = [];
        try { openedOrders = JSON.parse(localStorage.getItem('opened_orders')) || []; } catch(e) {}

        function initApp() {
            let driverData = null;
            try { driverData = localStorage.getItem('safar_driver'); } catch(e) {}
            
            if (driverData) {
                try {
                    let parsed = JSON.parse(driverData);
                    if (parsed && parsed.name) {
                        showDashboard(parsed);
                        return;
                    }
                } catch(e) {}
            }
            
            document.getElementById('registerScreen').style.display = 'block';
            document.getElementById('dashboardApp').style.display = 'none';
        }

        initApp();

        function submitRegistration() {
            let nameInput = document.getElementById('reg_name');
            let phoneInput = document.getElementById('reg_phone');
            let carModelInput = document.getElementById('reg_car_model');
            let carPlateInput = document.getElementById('reg_car_plate');

            let name = nameInput ? nameInput.value.trim() : "";
            let phone = phoneInput ? phoneInput.value.trim() : "";
            let carModel = carModelInput ? carModelInput.value.trim() : "";
            let carPlate = carPlateInput ? carPlateInput.value.trim() : "";

            if (!name || !phone || !carModel || !carPlate) {
                alert("Iltimos, barcha kataklarni to'ldiring!");
                return;
            }

            let data = {
                name: name,
                phone: phone,
                car_model: carModel,
                car_plate: carPlate,
                balance: 15000
            };

            try { localStorage.setItem('safar_driver', JSON.stringify(data)); } catch(e) {}
            
            showDashboard(data);
        }

        function showDashboard(data) {
            let regScreen = document.getElementById('registerScreen');
            let dashApp = document.getElementById('dashboardApp');

            if(regScreen) regScreen.style.display = 'none';
            if(dashApp) dashApp.style.display = 'block';

            document.getElementById('h_name').innerText = data.name || 'Haydovchi';
            document.getElementById('h_car').innerText = (data.car_model || '') + ' (' + (data.car_plate || '') + ')';
            document.getElementById('p_phone').innerText = data.phone || '';
            document.getElementById('p_car').innerText = data.car_model || '';
            document.getElementById('p_plate').innerText = data.car_plate || '';
            document.getElementById('p_balance').innerText = data.balance || 0;
            document.getElementById('b_balance').innerText = data.balance || 0;

            switchTab(1);
        }

        async function loadOrders() {
            let listEl = document.getElementById('ordersList');
            try {
                let res = await fetch('/api/orders');
                let orders = await res.json();
                
                if(!orders || orders.length === 0) {
                    listEl.innerHTML = '<p style="text-align: center; color: #777;">Hozircha buyurtmalar yo\'q.</p>';
                    return;
                }

                let html = '';
                orders.forEach(o => {
                    let isOpened = openedOrders.includes(o.id);
                    let phoneStr = isOpened ? '<b>📞 Tel:</b> +' + o.phone : '<b>📞 Tel:</b> +998****** (Yopiq)';
                    let btnHtml = isOpened ? '<p style="color:#10b981; font-weight:bold; margin-top:6px;">✅ Raqam ochilgan</p>' : '<button type="button" class="buy-btn" onclick="buyOrder(\'' + o.id + '\')">🔓 Raqamni ochish (3,000 so\'m)</button>';

                    html += '<div class="order-card">' +
                            '<div class="order-title"><span>📍 ' + o.from_city + ' ➡️ ' + o.to_city + '</span><span style="color:var(--accent-color);">' + o.price + ' so\'m</span></div>' +
                            '<div class="order-info"><b>Turi:</b> ' + o.type + ' (' + o.passengers + ')</div>' +
                            '<div class="order-info"><b>Mijoz:</b> ' + o.name + '</div>' +
                            '<div class="order-info">' + phoneStr + '</div>' +
                            '<div class="order-info"><b>Izoh:</b> ' + o.comment + '</div>' +
                            btnHtml +
                            '</div>';
                });
                listEl.innerHTML = html;
            } catch(e) {
                listEl.innerHTML = '<p style="text-align: center; color: red;">Xatolik yuz berdi.</p>';
            }
        }

        function buyOrder(orderId) {
            let driverData = JSON.parse(localStorage.getItem('safar_driver'));
            if (!driverData || driverData.balance < 3000) {
                alert("⚠️ Balansingizda yetarli mablag' yo'q!");
                switchTab(4);
                return;
            }

            if (confirm("Raqamni ochish uchun 3,000 so'm yechilsinmi?")) {
                driverData.balance -= 3000;
                localStorage.setItem('safar_driver', JSON.stringify(driverData));
                
                openedOrders.push(orderId);
                localStorage.setItem('opened_orders', JSON.stringify(openedOrders));

                document.getElementById('p_balance').innerText = driverData.balance;
                document.getElementById('b_balance').innerText = driverData.balance;
                loadOrders();
            }
        }

        function switchTab(tabNum) {
            document.querySelectorAll('#dashboardApp .screen-block').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

            let targetTab = document.getElementById('tab' + tabNum);
            if (targetTab) targetTab.classList.add('active');
            
            if(tabNum === 3) loadOrders();
            
            let navItems = document.querySelectorAll('.nav-item');
            if (navItems[tabNum - 1]) navItems[tabNum - 1].classList.add('active');
        }

        function clearData() {
            if (confirm("Ma'lumotlarni o'chirasizmi?")) {
                localStorage.clear();
                location.reload();
            }
        }

        function topUp(amount) {
            let driverData = JSON.parse(localStorage.getItem('safar_driver'));
            if(!driverData) driverData = { balance: 0 };
            driverData.balance = (driverData.balance || 0) + amount;
            localStorage.setItem('safar_driver', JSON.stringify(driverData));
            document.getElementById('p_balance').innerText = driverData.balance;
            document.getElementById('b_balance').innerText = driverData.balance;
            alert("✅ Balans to'ldirildi!");
        }
    </script>
</body>
</html>
"""
    html_content = html_template.replace("{{OPTIONS_HTML}}", options_html)
    return web.Response(text=html_content, content_type='text/html')

async def handle_home(request):
    return web.Response(text="Safar Taxi Bot ishlamoqda!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_home)
    app.router.add_get("/driver-app", handle_driver_app)
    app.router.add_get("/api/orders", handle_get_orders)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot va Zamonaviy Mini App ishga tushdi...")
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
