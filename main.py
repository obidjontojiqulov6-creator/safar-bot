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

ADMIN_ID = 123456789  # O'zingizning Telegram ID raqamingizni kiriting

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

    # 1. Yo'lovchi tanlanganda:
    if text in ["👤 Yo'lovchi", "👤 Пассажир"]:
        await state.set_state(BookingState.waiting_for_from_city)
        builder = ReplyKeyboardBuilder()
        for city in CITIES:
            builder.button(text=city)
        builder.adjust(2, 2, 2, 2, 2, 2)

        city_text = "📍 Qayerdan jo'naysiz? Hududni tanlang:" if lang == "uz" else "📍 Откуда выезжаете? Выберите регион:"
        return await message.answer(city_text, reply_markup=builder.as_markup(resize_keyboard=True))

    # 2. Haydovchi kabineti tanlanganda:
    elif text in ["🚖 Haydovchi kabineti", "🚖 Кабинет водителя"]:
        driver_id = message.from_user.id
        
        render_url = os.getenv("RENDER_EXTERNAL_URL", "")
        webapp_url = f"{render_url}/driver-form?lang={lang}&user_id={driver_id}"
        
        inline_builder = InlineKeyboardBuilder()
        inline_builder.button(
            text="📝 Anketani to'ldirish (Mini App)" if lang == "uz" else "📝 Заполнить анкету (Mini App)",
            web_app=types.WebAppInfo(url=webapp_url)
        )
        
        intro_text = (
            "🚖 **Haydovchi kabineti**\n\n"
            "Ro'yxatdan o'tish va buyurtmalarni ko'rish uchun pastdagi tugmani bosing va anketani to'ldiring:"
            if lang == "uz" else
            "🚖 **Кабинет водителя**\n\n"
            "Для регистрации нажмите на кнопку ниже и заполните анкету:"
        )
        return await message.answer(intro_text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")

    else:
        err = "Iltimos, tugmalardan birini tanlang!" if lang == "uz" else "Пожалуйста, выберите с помощью кнопок!"
        return await message.answer(err)

# --- MINI APP DAN KELGAN HAYDOVCHI MA'LUMOTLARini QABUL QILISH ---
@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        driver_id = message.from_user.id
        
        DRIVERS[driver_id] = {
            "name": data.get("name"),
            "phone": data.get("phone"),
            "car": data.get("car"),
            "current_city": data.get("from_city"),
            "target_city": data.get("to_city"),
            "lang": data.get("lang", "uz")
        }

        lang = data.get("lang", "uz")
        msg = "✅ Anketangiz qabul qilindi! Haydovchi sifatida ro'yxatdan o'tdingiz." if lang == "uz" else "✅ Ваши данные приняты! Вы зарегистрированы как водитель."
        await message.answer(msg)
    except Exception:
        await message.answer("❌ Ma'lumotlarni saqlashda xatolik yuz berdi.")

# --- YO'LOVCHI SO'ROVNOMASI ---
@dp.message(BookingState.waiting_for_from_city)
async def select_from_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    
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
        builder.adjust(2, 2, 2, 2, 2, 2)
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

    if text_in_back := (message.text in ["🔙 Orqaga", "🔙 Назад"]):
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
        "phone": phone
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

# --- WEB SERVER VA HAYDOVCHI MINI APP HTML KODI ---
async def handle_driver_form(request):
    lang = request.query.get("lang", "uz")
    
    options_html = "".join([f'<option value="{c}">{c}</option>' for c in CITIES])
    title = "Haydovchi Anketasi" if lang == "uz" else "Анкета Водителя"
    lbl_name = "Ism va Familiya:" if lang == "uz" else "Имя и Фамилия:"
    ph_name = "Masalan: Sardor Rahimov" if lang == "uz" else "Например: Сардор Рахимов"
    lbl_phone = "Telefon raqam:" if lang == "uz" else "Номер телефона:"
    lbl_car = "Mashina rusumi va raqami:" if lang == "uz" else "Модель и номер машины:"
    lbl_from = "Hozirgi shahar (Jo'nash):" if lang == "uz" else "Текущий город (Откуда):"
    lbl_to = "Boradigan shahar:" if lang == "uz" else "Город назначения (Куда):"
    btn_text = "Ro'yxatdan o'tish" if lang == "uz" else "Зарегистрироваться"

    html_content = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
        button {{
            width: 100%; background-color: var(--tg-theme-button-color, #0088cc);
            color: var(--tg-theme-button-text-color, #fff); border: none;
            padding: 14px; border-radius: 10px; font-size: 16px; font-weight: bold;
            cursor: pointer; margin-top: 24px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h2>🚖 {title}</h2>
        <form id="driverForm">
            <label>{lbl_name}</label>
            <input type="text" id="name" required placeholder="{ph_name}">

            <label>{lbl_phone}</label>
            <input type="tel" id="phone" required placeholder="+998901234567">

            <label>{lbl_car}</label>
            <input type="text" id="car" required placeholder="Gentra 01 A 777 AA">

            <label>{lbl_from}</label>
            <select id="from_city">
                {options_html}
            </select>

            <label>{lbl_to}</label>
            <select id="to_city">
                {options_html}
            </select>

            <button type="submit">{btn_text}</button>
        </form>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();

        document.getElementById('driverForm').addEventListener('submit', function(e) {{
            e.preventDefault();
            let data = {{
                name: document.getElementById('name').value,
                phone: document.getElementById('phone').value,
                car: document.getElementById('car').value,
                from_city: document.getElementById('from_city').value,
                to_city: document.getElementById('to_city').value,
                lang: "{lang}"
            }};
            tg.sendData(JSON.stringify(data));
            tg.close();
        }});
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
        web.get("/driver-form", handle_driver_form)
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot va Haydovchi Mini App serveri ishga tushdi...")
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
