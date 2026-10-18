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

    # Haydovchi tanlansa -> Mini App oynasini ochish uchun WebApp tugmasini chiqaramiz
    elif text in ["🚖 Haydovchi kabineti", "🚖 Кабинет водителя"]:
        driver_id = message.from_user.id
        
        # Render serveringizning asosiy URL manzili (avtomatik aniqlanadi yoki Render domeni yoziladi)
        # Hozircha Render'dagi web serverimiz ishlayotgan manzilga ulaymiz
        web_app_url = "https://your-render-app-url.onrender.com/driver-form" # Keyin bu yerga o'z Render havolangizni yozasiz
        
        inline_builder = InlineKeyboardBuilder()
        # Telegram Web App tugmasi
        inline_builder.button(
            text="📱 Haydovchi Mini App ochish" if lang == "uz" else "📱 Открыть Мини Приложение",
            web_app=types.WebAppInfo(url="https://google.com") # Vaqtincha test uchun, keyin o'z sahifamizga ulaymiz
        )
        
        intro_text = (
            "🚖 **Haydovchi kabineti (Mini App)**\n\n"
            "Ro'yxatdan o'tish va anketa to'ldirish uchun pastdagi tugmani bosing:"
            if lang == "uz" else
            "🚖 **Кабинет водителя (Мини Приложение)**\n\n"
            "Нажмите кнопку ниже для регистрации:"
        )
        return await message.answer(intro_text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")
    
    else:
        err = "Iltimos, tugmalardan birini tanlang!" if lang == "uz" else "Пожалуйста, выберите с помощью кнопок!"
        return await message.answer(err)

# --- WEB SERVER VA MINI APP SAHIFASI ---
async def handle_home(request):
    return web.Response(text="Bot va Mini App serveri ishlab turibdi!")

async def handle_driver_form(request):
    # Bu yerda haydovchilar ro'yxatdan o'tadigan chiroyli HTML sahifa (Mini App) qaytariladi
    html_content = """
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Haydovchi Anketasi</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: Arial, sans-serif; background: #f4f4f9; padding: 20px; color: #333; }
            .container { background: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); max-width: 400px; margin: auto; }
            h2 { text-align: center; color: #0088cc; }
            label { font-weight: bold; display: block; margin-top: 10px; }
            input, select { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
            button { width: 100%; background: #0088cc; color: white; border: none; padding: 12px; border-radius: 6px; margin-top: 20px; font-size: 16px; cursor: pointer; }
            button:hover { background: #006699; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🚖 Haydovchi Anketasi</h2>
            <form id="driverForm">
                <label>Ism va Familiya:</label>
                <input type="text" id="name" required placeholder="Masalan: Sardor Rahimov">

                <label>Telefon raqam:</label>
                <input type="tel" id="phone" required placeholder="+998901234567">

                <label>Mashina rusumi va raqami:</label>
                <input type="text" id="car" required placeholder="Cobalt 01 A 777 AA">

                <label>Hozirgi shahar (Jo'nash):</label>
                <select id="from_city">
                    <option value="Toshkent">Toshkent</option>
                    <option value="Andijon">Andijon</option>
                    <option value="Buxoro">Buxoro</option>
                    <option value="Samarqand">Samarqand</option>
                    <option value="Namangan">Namangan</option>
                </select>

                <label>Boradigan shahar:</label>
                <select id="to_city">
                    <option value="Andijon">Andijon</option>
                    <option value="Toshkent">Toshkent</option>
                    <option value="Buxoro">Buxoro</option>
                    <option value="Samarqand">Samarqand</option>
                    <option value="Namangan">Namangan</option>
                </select>

                <button type="submit">Ro'yxatdan o'tish</button>
            </form>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand(); // Oynani to'liq ochish

            document.getElementById('driverForm').addEventListener('submit', function(e) {
                e.preventDefault();
                let data = {
                    name: document.getElementById('name').value,
                    phone: document.getElementById('phone').value,
                    car: document.getElementById('car').value,
                    from_city: document.getElementById('from_city').value,
                    to_city: document.getElementById('to_city').value
                };
                tg.sendData(JSON.stringify(data)); // Ma'lumotni botga yuborish
                tg.close(); // Oynani yopish
            });
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

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
    print("Bot va Mini App veb-serveri ishga tushdi...")
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.main() if hasattr(asyncio, "main") else asyncio.run(main())
