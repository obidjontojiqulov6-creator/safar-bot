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

# Namuna buyurtmalar
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

CITIES_UZ = [
    "Toshkent", "Andijon", "Buxoro", "Jizzax", 
    "Navoiy", "Namangan", "Qarshi", "Samarqand", 
    "Guliston", "Termiz", "Urganch", "Nukus"
]

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip('/')
    if not render_url:
        render_url = "https://safar-taxi.onrender.com"
    webapp_url = f"{render_url}/driver-app?user_id={user_id}"
    
    inline_builder = InlineKeyboardBuilder()
    inline_builder.button(
        text="🚖 Haydovchi Kabineti (Mini App)",
        web_app=types.WebAppInfo(url=webapp_url)
    )
    
    await message.answer(
        "🇺🇿 **Safar Taxi** haydovchi botiga xush kelibsiz!\n\n"
        "Buyurtmalarni ko'rish va kabinetga kirish uchun pastdagi tugmani bosing:",
        reply_markup=inline_builder.as_markup(),
        parse_mode="Markdown"
    )

async def handle_get_orders(request):
    return web.json_response(list(ORDERS.values()))

async def handle_driver_app(request):
    options_html = "".join([f'<option value="{c}">{c}</option>' for c in CITIES_UZ])

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
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* Yuqori qism - Header */
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

        /* Kartochkalar */
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

        button {
            width: 100%; background: var(--accent-gradient);
            color: #000000; border: none;
            padding: 14px; border-radius: 12px; font-size: 15px; font-weight: 800;
            cursor: pointer; margin-top: 16px;
            box-shadow: 0 4px 15px rgba(245, 158, 11, 0.3);
        }
        .reset-btn { background: #ef4444 !important; color: #fff !important; margin-top: 20px; }

        /* Buyurtma kartasi */
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
            margin-top: 10px; border-radius: 8px; box-shadow: none;
        }

        /* Pastki Navigatsiya Menu */
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

    <!-- RO'YXATDAN O'TISH -->
    <div id="registerScreen" class="tab-content active">
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

            <button type="button" onclick="submitRegistration()">Ro'yxatdan o'tish</button>
        </div>
    </div>

    <!-- ASOSIY DASHBOARD -->
    <div id="dashboardApp" style="display: none;">
        
        <!-- Header Profil qisqacha -->
        <div class="header-card">
            <div class="driver-info">
                <h3 id="h_name">Haydovchi</h3>
                <p id="h_car">Mashina ma'lumoti</p>
            </div>
            <div class="balance-badge"><span id="p_balance">15000</span> so'm</div>
        </div>

        <!-- 1-BO'LIM: PROFIL -->
        <div id="tab1" class="tab-content active">
            <div class="card">
                <h2>👤 Mening Profilim</h2>
                <p><b>📞 Tel:</b> <span id="p_phone"></span></p>
                <p><b>🚗 Mashina:</b> <span id="p_car"></span> (<span id="p_plate"></span>)</p>
                <button type="button" class="reset-btn" onclick="clearData()">🔄 Qaytadan ro'yxatdan o'tish</button>
            </div>
        </div>

        <!-- 2-BO'LIM: YO'NALISH -->
        <div id="tab2" class="tab-content">
            <div class="card">
                <h2>⚙️ Yo'nalish sozlamalari</h2>
                <label>Jo'nash shahri:</label>
                <select id="set_from">{{OPTIONS_HTML}}</select>

                <label>Boradigan shahar:</label>
                <select id="set_to">{{OPTIONS_HTML}}</select>

                <label>1 odam uchun narx (so'm):</label>
                <input type="number" id="set_min_price" value="50000">

                <button type="button" onclick="saveSettings()">Saqlash</button>
            </div>
        </div>

        <!-- 3-BO'LIM: BUYURTMALAR -->
        <div id="tab3" class="tab-content">
            <div class="card">
                <h2>👥 Mos Buyurtmalar</h2>
                <div id="ordersList">
                    <p style="text-align: center; color: #777;">Yuklanmoqda...</p>
                </div>
            </div>
        </div>

        <!-- 4-BO'LIM: BALANS -->
        <div id="tab4" class="tab-content">
            <div class="card">
                <h2>💳 Balansni to'ldirish</h2>
                <p>Joriy balans: <b id="b_balance" style="color: var(--accent-color);">0</b> so'm</p>
                <label>Summani tanlang:</label>
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
            let name = document.getElementById('reg_name').value.trim();
            let phone = document.getElementById('reg_phone').value.trim();
            let carModel = document.getElementById('reg_car_model').value.trim();
            let carPlate = document.getElementById('reg_car_plate').value.trim();

            if (!name || !phone || !carModel || !carPlate) {
                alert("Iltimos, barcha maydonlarni to'ldiring!");
                return;
            }

            let data = {
                name: name, phone: phone, car_model: carModel, car_plate: carPlate, balance: 15000
            };

            try { localStorage.setItem('safar_driver', JSON.stringify(data)); } catch(e) {}
            showDashboard(data);
        }

        function showDashboard(data) {
            document.getElementById('registerScreen').style.display = 'none';
            document.getElementById('dashboardApp').style.display = 'block';

            document.getElementById('h_name').innerText = data.name;
            document.getElementById('h_car').innerText = data.car_model + ' (' + data.car_plate + ')';
            document.getElementById('p_phone').innerText = data.phone;
            document.getElementById('p_car').innerText = data.car_model;
            document.getElementById('p_plate').innerText = data.car_plate;
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
            document.querySelectorAll('#dashboardApp .tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

            document.getElementById('tab' + tabNum).classList.add('active');
            if(tabNum === 3) loadOrders();
            document.querySelectorAll('.nav-item')[tabNum - 1].classList.add('active');
        }

        function clearData() {
            if (confirm("Ma'lumotlarni o'chirasizmi?")) {
                localStorage.clear();
                location.reload();
            }
        }

        function topUp(amount) {
            let driverData = JSON.parse(localStorage.getItem('safar_driver'));
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
