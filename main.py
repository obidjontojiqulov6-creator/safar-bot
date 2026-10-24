import os
import asyncio
import logging
import json
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiohttp import web

# --- 1. SOZLAMALAR ---
PASSENGER_TOKEN = os.getenv("BOT_TOKEN")
DRIVER_TOKEN = os.getenv("DRIVER_BOT_TOKEN")

RENDER_BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "https://safar-taxi-zocf.onrender.com").rstrip('/')

passenger_bot = Bot(token=PASSENGER_TOKEN)
driver_bot = Bot(token=DRIVER_TOKEN)

dp_passenger = Dispatcher(storage=MemoryStorage())
dp_driver = Dispatcher(storage=MemoryStorage())

# Ma'lumotlar bazasi
DATA = {
    "orders": {},
    "drivers": {}
}

# --- 2. YO'LOVCHI BOTI HOLATLARI (FSM) ---
class OrderState(StatesGroup):
    language = State()       # 1. Tilni tanlash
    service_type = State()   # 2. Yo'lovchi yoki Dastavka
    from_city = State()      # 3. Qayerdan
    to_city = State()        # 4. Qayerga
    comment = State()        # 5. Izoh
    location = State()       # 6. Joylashuv (Lokatsiya)
    phone = State()          # 7. Telefon raqam

# --- 3. YO'LOVCHILAR BOTI LOGIKASI ---

@dp_passenger.message(Command("start"))
async def cmd_start_passenger(message: types.Message, state: FSMContext):
    await state.clear()
    
    # 1-Bosqich: Salomlashish va Tilni tanlash
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.adjust(2)

    await message.answer(
        "👋 Assalomu alaykum! **Safar Taxi** botiga xush kelibsiz.\n"
        "Iltimos, tilni tanlang / Пожалуйста, выберите язык:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await state.set_state(OrderState.language)

@dp_passenger.callback_query(OrderState.language, F.data.startswith("lang_"))
async def process_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(lang=lang)
    
    # 2-Bosqich: Xizmat turini tanlash
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚖 Yo'lovchi")
    builder.button(text="📦 Dastavka")
    builder.adjust(2)

    msg = "Xizmat turini tanlang:" if lang == "uz" else "Выберите тип службы:"
    await callback.message.answer(msg, reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(OrderState.service_type)
    await callback.answer()

@dp_passenger.message(OrderState.service_type)
async def process_service_type(message: types.Message, state: FSMContext):
    await state.update_data(service_type=message.text)
    
    # 3-Bosqich: Qayerdan
    await message.answer("📍 Qayerdan yo'lga chiqasiz? (Masalan: Toshkent)", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(OrderState.from_city)

@dp_passenger.message(OrderState.from_city)
async def process_from_city(message: types.Message, state: FSMContext):
    await state.update_data(from_city=message.text)
    
    # 4-Bosqich: Qayerga
    await message.answer("🏁 Qayerga borasiz? (Masalan: Samarqand)")
    await state.set_state(OrderState.to_city)

@dp_passenger.message(OrderState.to_city)
async def process_to_city(message: types.Message, state: FSMContext):
    await state.update_data(to_city=message.text)
    
    # 5-Bosqich: Izoh
    await message.answer("📝 Izoh va tafsilotlarni kiriting (Masalan: 2 kishi, sumka bor, narxi 100,000 so'm):")
    await state.set_state(OrderState.comment)

@dp_passenger.message(OrderState.comment)
async def process_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=message.text)
    
    # 6-Bosqich: Lokatsiya
    builder = ReplyKeyboardBuilder()
    builder.button(text="📍 Hozirgi joylashuvni yuborish", request_location=True)
    
    await message.answer("📍 Turgan joyingiz (lokatsiya)ni yuboring:", reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True))
    await state.set_state(OrderState.location)

@dp_passenger.message(OrderState.location)
async def process_location(message: types.Message, state: FSMContext):
    if message.location:
        loc_data = f"{message.location.latitude},{message.location.longitude}"
    else:
        loc_data = message.text
        
    await state.update_data(location=loc_data)
    
    # 7-Bosqich: Telefon raqam
    builder = ReplyKeyboardBuilder()
    builder.button(text="📞 Telefon raqamni yuborish", request_contact=True)
    
    await message.answer("📞 Telefon raqamingizni yuboring:", reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True))
    await state.set_state(OrderState.phone)

@dp_passenger.message(OrderState.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    user_data = await state.get_data()
    
    order_id = str(len(DATA["orders"]) + 1)
    
    # Buyurtmani saqlash
    DATA["orders"][order_id] = {
        "id": order_id,
        "service_type": user_data.get("service_type", "Yo'lovchi"),
        "from_city": user_data.get("from_city", "-"),
        "to_city": user_data.get("to_city", "-"),
        "comment": user_data.get("comment", "-"),
        "location": user_data.get("location", "-"),
        "phone": phone,
        "passengers": "👨 Yo'lovchi" if "Yo'lovchi" in user_data.get("service_type", "") else "📦 Pochta",
        "price": "Kelisilgan",
        "name": message.from_user.full_name,
        "time": time.strftime("%H:%M")
    }
    
    await message.answer(
        f"✅ **Buyurtmangiz qabul qilindi!**\n\n"
        f"🆔 **Buyurtma ID:** #{order_id}\n"
        f"🚕 **Xizmat:** {user_data.get('service_type')}\n"
        f"📍 **Yo'nalish:** {user_data.get('from_city')} ➡️ {user_data.get('to_city')}\n"
        f"📝 **Izoh:** {user_data.get('comment')}\n"
        f"📞 **Tel:** {phone}\n\n"
        f"Haydovchilar tez orada siz bilan bog'lanishadi!",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await state.clear()

# --- 4. HAYDOVCHILAR BOTI LOGIKASI ---

@dp_driver.message(Command("start"))
async def cmd_start_driver(message: types.Message):
    webapp_url = f"{RENDER_BASE_URL}/driver-app?user_id={message.from_user.id}&v={int(time.time())}"
    
    inline_builder = InlineKeyboardBuilder()
    inline_builder.button(
        text="🚖 Haydovchi Kabineti (Mini App)",
        web_app=types.WebAppInfo(url=webapp_url)
    )
    
    await message.answer(
        "🇺🇿 **Safar Taxi** haydovchilar botiga xush kelibsiz!\n\n"
        "Yo'lovchilar buyurtmalarini ko'rish va hisobingizni boshqarish uchun pastdagi tugmani bosing:",
        reply_markup=inline_builder.as_markup(),
        parse_mode="Markdown"
    )

# --- 5. VEB SERVER VA MINI APP INTERFEYSI ---

async def handle_get_orders(request):
    return web.json_response(list(DATA["orders"].values()))

async def handle_driver_app(request):
    cities_list = ["Toshkent", "Samarqand", "Buxoro", "Andijon", "Farg'ona", "Namangan", "Qarshi", "Nukus"]
    options_html = "".join([f'<option value="{c}">{c}</option>' for c in cities_list])

    html_template = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Safar Driver</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #0b0c10; --text: #ffffff; --text-sec: #a0a5b5; --accent: #ff3b5c; --border: rgba(255,255,255,0.08); }
        body { font-family: -apple-system, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 16px; padding-bottom: 50px; }
        
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 22px; font-weight: 800; }
        .header p { margin: 4px 0 0; font-size: 13px; color: var(--text-sec); }

        .banner { background: linear-gradient(135deg, #ff3b5c, #e60039); border-radius: 20px; padding: 18px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .btn-white { background: #fff; color: #e60039; border: none; padding: 10px 18px; border-radius: 12px; font-weight: bold; cursor: pointer; }

        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
        .card { border-radius: 18px; padding: 15px 10px; height: 100px; display: flex; flex-direction: column; justify-content: space-between; position: relative; cursor: pointer; }
        .card-icon { font-size: 24px; }
        .card-title { font-size: 13px; font-weight: 700; }
        
        .c-cyan { background: linear-gradient(135deg, #00c6ff, #0072ff); }
        .c-purple { background: linear-gradient(135deg, #a855f7, #6b21a8); }
        .c-gold { background: linear-gradient(135deg, #eab308, #a16207); }
        .c-green { background: linear-gradient(135deg, #10b981, #047857); }
        .c-orange { background: linear-gradient(135deg, #f97316, #c2410c); }
        .c-red { background: linear-gradient(135deg, #ef4444, #b91c1c); }

        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; overflow-y: auto; }
        .modal.active { display: block; }
        .modal-content { background: #161820; border-radius: 20px 20px 0 0; position: absolute; bottom: 0; left: 0; width: 100%; min-height: 80%; padding: 20px; box-sizing: border-box; }
        .close-btn { background: rgba(255,255,255,0.1); color: #fff; border: none; padding: 8px 12px; border-radius: 10px; font-weight: bold; margin-bottom: 15px; cursor: pointer; }
        
        .order-item { background: #212430; border-radius: 12px; padding: 12px; margin-bottom: 10px; border-left: 3px solid #00c6ff; }
    </style>
</head>
<body>

    <div class="header">
        <div><h1>Haydovchi</h1><p>Safar Taxi boshqaruv paneli</p></div>
    </div>

    <div class="banner">
        <div><h3>Balans: <span id="bal1">15,000</span> s.</h3><p>Raqam ochish: 3,000 s.</p></div>
        <button class="btn-white" onclick="openP('p_bal')">To'ldirish</button>
    </div>

    <div class="grid">
        <div class="card c-cyan" onclick="openP('p_ord')"><div class="card-icon">🚖</div><div class="card-title">Yo'lovchilar</div></div>
        <div class="card c-purple" onclick="openP('p_del')"><div class="card-icon">📦</div><div class="card-title">Dastavka</div></div>
        <div class="card c-gold" onclick="openP('p_rou')"><div class="card-icon">⚙️</div><div class="card-title">Yo'nalish</div></div>
        <div class="card c-green" onclick="openP('p_bal')"><div class="card-icon">💳</div><div class="card-title">Balans</div></div>
        <div class="card c-orange" onclick="openP('p_pro')"><div class="card-icon">🚗</div><div class="card-title">Profil</div></div>
        <div class="card c-red" onclick="alert('Admin: @SafarTaxiAdmin')"><div class="card-icon">🎧</div><div class="card-title">Yordam</div></div>
    </div>

    <div id="p_ord" class="modal"><div class="modal-content"><button class="close-btn" onclick="closeP()">⬅️ Orqaga</button><h3>Yo'lovchi buyurtmalari</h3><div id="ordList">Yuklanmoqda...</div></div></div>
    <div id="p_del" class="modal"><div class="modal-content"><button class="close-btn" onclick="closeP()">⬅️ Orqaga</button><h3>Dastavka buyurtmalari</h3><div id="delList">Yuklanmoqda...</div></div></div>

    <script>
        function openP(id) { document.querySelectorAll('.modal').forEach(m=>m.classList.remove('active')); document.getElementById(id).classList.add('active'); if(id==='p_ord' || id==='p_del') loadOrd(id==='p_del'); }
        function closeP() { document.querySelectorAll('.modal').forEach(m=>m.classList.remove('active')); }
        
        async function loadOrd(isDel) {
            let list = document.getElementById(isDel?'delList':'ordList');
            try {
                let res = await fetch('/api/orders');
                let orders = await res.json();
                let html = '';
                orders.forEach(o => {
                    let isDelivery = o.service_type.includes('Dastavka') || o.passengers.includes('📦');
                    if(isDel === isDelivery) {
                        html += `<div class="order-item"><b>📍 ${o.from_city} ➡️ ${o.to_city}</b><br><small>👤 Mijoz: ${o.name}</small><br><small>📞 Tel: ${o.phone}</small><br><small>📝 Izoh: ${o.comment}</small><br><small>📍 Lokatsiya: ${o.location}</small></div>`;
                    }
                });
                list.innerHTML = html || '<p>Hozircha buyurtmalar yo\'q</p>';
            } catch(e) { list.innerHTML = '<p>Yuklashda xatolik</p>'; }
        }
    </script>
</body>
</html>
"""
    return web.Response(text=html_template.replace("{{CITIES}}", options_html), content_type='text/html')

async def handle_home(request):
    return web.Response(text="Safar Taxi Dual Bot ishlamoqda!")

# --- 6. ISHGA TUSHIRISH ---
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
    await asyncio.gather(
        web_server(),
        dp_passenger.start_polling(passenger_bot),
        dp_driver.start_polling(driver_bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
