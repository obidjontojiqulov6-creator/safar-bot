import os
import asyncio
import logging
import json
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# --- 1. SOZLAMALAR ---
PASSENGER_TOKEN = os.getenv("BOT_TOKEN")
DRIVER_TOKEN = os.getenv("DRIVER_BOT_TOKEN")

# Render dagi asosiy veb-server havolangiz
RENDER_BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "https://safar-taxi-zocf.onrender.com").rstrip('/')

passenger_bot = Bot(token=PASSENGER_TOKEN)
driver_bot = Bot(token=DRIVER_TOKEN)
dp = Dispatcher()

# Vaqtinchalik ma'lumotlar bazasi
DATA = {
    "orders": {},
    "drivers": {}
}

# --- 2. YO'LOVCHILAR BOTI LOGIKASI (@Safar_bot_zocf) ---

@dp.message(Command("start"), F.bot.id == passenger_bot.id)
async def cmd_start_passenger(message: types.Message):
    await message.answer(
        "👋 Assalomu alaykum! **Safar Taxi** yo'lovchilar botiga xush kelibsiz.\n\n"
        "Buyurtma berish uchun quyidagi ma'lumotlarni yuboring:\n"
        "1. Qayerdan (shahar)\n"
        "2. Qayerga\n"
        "3. Necha kishi yoki yuk\n"
        "4. Narx va telefon raqamingiz\n\n"
        "Masalan: _Toshkent ➡️ Buxoro, 2 kishi, 150,000 so'm, +998901234567_",
        parse_mode="Markdown"
    )

@dp.message(F.text, F.bot.id == passenger_bot.id)
async def handle_new_order(message: types.Message):
    order_id = str(len(DATA["orders"]) + 1)
    DATA["orders"][order_id] = {
        "id": order_id,
        "from_city": "Toshkent",
        "to_city": "Samarqand",
        "passengers": "👨 2 kishi",
        "price": "100,000",
        "phone": message.from_user.username or "Mavjud emas",
        "comment": message.text[:60],
        "time": time.strftime("%H:%M")
    }
    
    await message.answer(f"✅ Buyurtmangiz qabul qilindi! Haydovchilarga uzatildi. (ID: {order_id})")

# --- 3. HAYDOVCHILAR BOTI LOGIKASI (@Safaryol_driver_bot) ---

@dp.message(Command("start"), F.bot.id == driver_bot.id)
async def cmd_start_driver(message: types.Message):
    webapp_url = f"{RENDER_BASE_URL}/driver-app?user_id={message.from_user.id}&v={int(time.time())}"
    
    inline_builder = InlineKeyboardBuilder()
    inline_builder.button(
        text="🚖 Haydovchi Kabineti (Mini App)",
        web_app=types.WebAppInfo(url=webapp_url)
    )
    
    await message.answer(
        "🇺🇿 **Safar Taxi** haydovchi botiga xush kelibsiz!\n\n"
        "Buyurtmalarni ko'rish va balansni boshqarish uchun pastdagi tugmani bosing:",
        reply_markup=inline_builder.as_markup(),
        parse_mode="Markdown"
    )

# --- 4. VEB SERVER VA MINI APP API ---

async def handle_get_orders(request):
    if not DATA["orders"]:
        DATA["orders"]["1"] = {
            "id": "1", "from_city": "Toshkent", "to_city": "Buxoro", 
            "passengers": "👨 2 kishi", "price": "150,000", 
            "phone": "+998901234567", "comment": "Sumka bor", "time": "14:00"
        }
        DATA["orders"]["2"] = {
            "id": "2", "from_city": "Toshkent", "to_city": "Andijon", 
            "passengers": "📦 10kg pochta", "price": "50,000", 
            "phone": "+998919876543", "comment": "Kichik quti", "time": "14:15"
        }
    return web.json_response(list(DATA["orders"].values()))

async def handle_driver_app(request):
    cities_list = ["Toshkent", "Samarqand", "Buxoro", "Andijon", "Farg'ona", "Namangan", "Qarshi", "Nukus"]
    options_html = "".join([f'<option value="{c}">{c}</option>' for c in cities_list])

    html_template = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <title>Safar Driver</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #0b0c10; --text: #ffffff; --text-sec: #a0a5b5; --accent: #ff3b5c; --border: rgba(255,255,255,0.08); }
        body { font-family: -apple-system, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 16px; padding-bottom: 50px; }
        
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 22px; font-weight: 800; }
        .header p { margin: 4px 0 0; font-size: 13px; color: var(--text-sec); }
        .lang { background: rgba(255,255,255,0.1); padding: 5px 10px; border-radius: 20px; font-size: 12px; }

        .banner { background: linear-gradient(135deg, #ff3b5c, #e60039); border-radius: 20px; padding: 18px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; box-shadow: 0 8px 20px rgba(230,0,57,0.2); }
        .banner h3 { margin: 0; font-size: 16px; }
        .banner p { margin: 3px 0 0; font-size: 12px; opacity: 0.8; }
        .btn-white { background: #fff; color: #e60039; border: none; padding: 10px 18px; border-radius: 12px; font-size: 13px; font-weight: bold; cursor: pointer; }

        .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
        .card { border-radius: 18px; padding: 15px 10px; height: 100px; display: flex; flex-direction: column; justify-content: space-between; position: relative; cursor: pointer; transition: transform 0.1s; }
        .card:active { transform: scale(0.96); }
        .card-icon { font-size: 24px; margin-bottom: 5px; }
        .card-title { font-size: 13px; font-weight: 700; }
        .card-sub { font-size: 10px; opacity: 0.7; }
        
        .c-cyan { background: linear-gradient(135deg, #00c6ff, #0072ff); }
        .c-purple { background: linear-gradient(135deg, #a855f7, #6b21a8); }
        .c-gold { background: linear-gradient(135deg, #eab308, #a16207); }
        .c-green { background: linear-gradient(135deg, #10b981, #047857); }
        .c-orange { background: linear-gradient(135deg, #f97316, #c2410c); }
        .c-red { background: linear-gradient(135deg, #ef4444, #b91c1c); }
        
        .badge { position: absolute; top: 8px; right: 8px; background: rgba(255,255,255,0.9); color: #000; font-size: 8px; font-weight: 900; padding: 2px 5px; border-radius: 5px; }

        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; overflow-y: auto; }
        .modal.active { display: block; }
        .modal-content { background: #161820; border-radius: 20px 20px 0 0; position: absolute; bottom: 0; left: 0; width: 100%; min-height: 80%; padding: 20px; box-sizing: border-box; }
        .close-btn { background: rgba(255,255,255,0.1); color: #fff; border: none; padding: 8px 12px; border-radius: 10px; font-weight: bold; margin-bottom: 15px; cursor: pointer; }
        
        input, select { width: 100%; padding: 12px; margin: 8px 0; background: #222; color: #fff; border: 1px solid var(--border); border-radius: 10px; box-sizing: border-box; }
        .btn-accent { width: 100%; padding: 12px; background: var(--accent); color: #fff; border: none; border-radius: 10px; font-weight: bold; margin-top: 10px; cursor: pointer; }
        
        .order-item { background: #212430; border-radius: 12px; padding: 12px; margin-bottom: 10px; border-left: 3px solid #00c6ff; }
    </style>
</head>
<body>

    <div class="header">
        <div><h1>Haydovchi</h1><p>Safar Taxi boshqaruv paneli</p></div>
        <div class="lang">🌐 UZ</div>
    </div>

    <div class="banner">
        <div><h3>Balans: <span id="bal1">15,000</span> s.</h3><p>Raqam ochish: 3,000 s.</p></div>
        <button class="btn-white" onclick="openP('p_bal')">To'ldirish</button>
    </div>

    <div class="grid">
        <div class="card c-cyan" onclick="openP('p_ord')"><div class="card-icon">🚖</div><div><div class="card-title">Yo'lovchilar</div><div class="card-sub">E'lonlar</div></div></div>
        <div class="card c-purple" onclick="openP('p_del')"><span class="badge">YANGI</span><div class="card-icon">📦</div><div><div class="card-title">Dastafka</div><div class="card-sub">Pochta & Yuk</div></div></div>
        <div class="card c-gold" onclick="openP('p_rou')"><div class="card-icon">⚙️</div><div><div class="card-title">Yo'nalish</div><div class="card-sub">Sozlash</div></div></div>
        <div class="card c-green" onclick="openP('p_bal')"><div class="card-icon">💳</div><div><div class="card-title">Balans</div><div class="card-sub">Hisob</div></div></div>
        <div class="card c-orange" onclick="openP('p_pro')"><div class="card-icon">🚗</div><div><div class="card-title">Profil</div><div class="card-sub">Mashina</div></div></div>
        <div class="card c-red" onclick="alert('Admin bilan aloqa: @SafarTaxiAdmin')"><div class="card-icon">🎧</div><div><div class="card-title">Yordam</div><div class="card-sub">Admin</div></div></div>
    </div>

    <!-- MODAL OYNALAR -->
    <div id="p_rou" class="modal"><div class="modal-content"><button class="close-btn" onclick="closeP()">⬅️ Orqaga</button><h3>Yo'nalish sozlash</h3><label>Jo'nash shahri:</label><select>{{CITIES}}</select><label>Borish shahri:</label><select>{{CITIES}}</select><button class="btn-accent" onclick="alert('Yo\\'nalish saqlandi!')">Saqlash</button></div></div>
    <div id="p_bal" class="modal"><div class="modal-content"><button class="close-btn" onclick="closeP()">⬅️ Orqaga</button><h3>Balansni to'ldirish</h3><p>Joriy hisob: <b id="bal2">15,000</b> so'm</p><div style="display:flex; gap:10px;"><button class="btn-accent" style="background:#10b981;" onclick="addBal(10000)">+10,000</button><button class="btn-accent" style="background:#10b981;" onclick="addBal(25000)">+25,000</button></div></div></div>
    <div id="p_pro" class="modal"><div class="modal-content"><button class="close-btn" onclick="closeP()">⬅️ Orqaga</button><h3>Haydovchi profili</h3><p><b>🚗 Mashina:</b> Cobalt (01 A 123 AA)</p><p><b>👤 Holati:</b> Tasdiqlangan</p></div></div>
    <div id="p_ord" class="modal"><div class="modal-content"><button class="close-btn" onclick="closeP()">⬅️ Orqaga</button><h3>Yo'lovchi buyurtmalari</h3><div id="ordList">Yuklanmoqda...</div></div></div>
    <div id="p_del" class="modal"><div class="modal-content"><button class="close-btn" onclick="closeP()">⬅️ Orqaga</button><h3>Dastafka buyurtmalari</h3><div id="delList">Yuklanmoqda...</div></div></div>

    <script>
        let tg = window.Telegram ? window.Telegram.WebApp : null;
        if(tg) { try { tg.expand(); } catch(e) {} }
        let currentBalance = 15000;

        function openP(id) { document.querySelectorAll('.modal').forEach(m=>m.classList.remove('active')); document.getElementById(id).classList.add('active'); if(id==='p_ord' || id==='p_del') loadOrd(id==='p_del'); }
        function closeP() { document.querySelectorAll('.modal').forEach(m=>m.classList.remove('active')); }
        function addBal(a) { currentBalance += a; updateBalUI(); alert("Balans to'ldirildi!"); }
        function updateBalUI() { document.getElementById('bal1').innerText = currentBalance.toLocaleString(); document.getElementById('bal2').innerText = currentBalance.toLocaleString(); }
        
        async function loadOrd(isDel) {
            let list = document.getElementById(isDel?'delList':'ordList');
            try {
                let res = await fetch('/api/orders');
                let orders = await res.json();
                let html = '';
                orders.forEach(o => {
                    let isDelivery = o.passengers.includes('📦');
                    if(isDel === isDelivery) {
                        html += `<div class="order-item"><b>📍 ${o.from_city} ➡️ ${o.to_city}</b> (${o.price} so'm)<br><small>👤 Mijoz: ${o.name}</small><br><small>📞 Tel: ${o.phone}</small><br><small>📝 ${o.comment}</small></div>`;
                    }
                });
                list.innerHTML = html || '<p>Hozircha buyurtmalar yo\\'q</p>';
            } catch(e) { list.innerHTML = '<p>Maʼlumotni yuklashda xatolik yuz berdi</p>'; }
        }
    </script>
</body>
</html>
"""
    html_content = html_template.replace("{{CITIES}}", options_html)
    return web.Response(text=html_content, content_type='text/html')

async def handle_home(request):
    return web.Response(text="Safar Taxi Dual Bot va Mini App ishlamoqda!")

# --- 5. SERVERNI ISHGA TUSHIRISH ---
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
    logging.info(f"Veb-server {port}-portda ishga tushdi.")

async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Safar Taxi botlari ishga tushirilmoqda...")
    await asyncio.gather(
        web_server(), 
        dp.start_polling(passenger_bot), 
        dp.start_polling(driver_bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
