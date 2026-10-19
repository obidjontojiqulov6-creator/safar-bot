import os
import asyncio
import logging
import json
import uuid
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

ADMIN_ID = 123456789  # Telegram ID raqamingiz

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
        DRIVERS[driver_id] = data
        lang = data.get("lang", "uz")
        msg = "✅ Ma'lumotlaringiz saqlandi!" if lang == "uz" else "✅ Ваши данные сохранены!"
        await message.answer(msg)
    except Exception:
        await message.answer("❌ Xatolik yuz berdi.")

# Rasm yuklash Endpoint
async def handle_upload(request):
    reader = await request.multipart()
    field = await reader.next()
    if not field:
        return web.json_response({"error": "No file uploaded"}, status=400)
    
    filename = f"{uuid.uuid4()}.jpg"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as f:
        while True:
            chunk = await field.read_chunk()
            if not chunk:
                break
            f.write(chunk)
            
    file_url = f"{request.scheme}://{request.host}/uploads/{filename}"
    return web.json_response({"url": file_url})

# Mini App HTML
async def handle_driver_app(request):
    lang = request.query.get("lang", "uz")
    cities = CITIES_UZ if lang == "uz" else CITIES_RU
    options_html = "".join([f'<option value="{c}">{c}</option>' for c in cities])

    if lang == "uz":
        t_reg = "Haydovchi Anketasi"
        l_name = "Ism va Familiya:"
        l_photo = "Profil rasmini tanlash:"
        l_phone = "Telefon raqam:"
        l_car = "Avtomobil rusumi va rangi:"
        l_plate = "Avtomobil davlat raqami:"
        l_car1 = "Mashina oldi tomoni rasmini tanlash:"
        btn_reg = "Ro'yxatdan o'tish"
        t_prof = "Mening Profilim"
        lbl_name = "Ism"
        lbl_tel = "Tel"
        lbl_car_str = "Mashina"
        lbl_bal = "Balans"
        t_set = "Yo'nalish va Sozlamalar"
        l_from = "Jo'nash shahri:"
        l_to = "Boradigan shahar:"
        l_pass_cnt = "Odamlar soni (Maksimal):"
        l_mode = "Ish tartibi (Dastavka / Yo'lovchi):"
        mode_1 = "🚖 Faqat yo'lovchi"
        mode_2 = "📦 Faqat dastafka (yuk)"
        mode_3 = "📦 ➡️ 🚖 Avval dastafka, keyin yo'lovchi"
        mode_4 = "🚖 ➡️ 📦 Avval yo'lovchi, keyin dastafka"
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
        reset_btn = "🔄 Ma'lumotlarni o'chirish va noldan boshlash"
    else:
        t_reg = "Анкета Водителя"
        l_name = "Имя и Фамилия:"
        l_photo = "Выберите фото профиля:"
        l_phone = "Номер телефона:"
        l_car = "Модель и цвет машины:"
        l_plate = "Гос. номер машины:"
        l_car1 = "Выберите фото машины спереди:"
        btn_reg = "Зарегистрироваться"
        t_prof = "Мой Профиль"
        lbl_name = "Имя"
        lbl_tel = "Тел"
        lbl_car_str = "Машина"
        lbl_bal = "Баланс"
        t_set = "Маршрут и Настройки"
        l_from = "Город отправления:"
        l_to = "Город назначения:"
        l_pass_cnt = "Количество пассажиров (Макс):"
        l_mode = "Режим работы (Доставка / Пассажир):"
        mode_1 = "🚖 Только пассажир"
        mode_2 = "📦 Только доставка (груз)"
        mode_3 = "📦 ➡️ 🚖 Сначала доставка, потом пассажир"
        mode_4 = "🚖 ➡️ 📦 Сначала пассажир, потом доставка"
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
        reset_btn = "🔄 Сбросить данные и начать заново"

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
        .tab-content.active {{ display: block !important; }}
        
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
        .reset-btn {{
            background-color: #e74c3c !important;
            margin-top: 20px;
        }}
        .profile-img {{ width: 90px; height: 90px; border-radius: 50%; object-fit: cover; display: block; margin: 0 auto 12px auto; border: 2px solid #0088cc; }}
        .car-big-img {{ width: 100%; height: 180px; border-radius: 10px; object-fit: cover; margin-top: 12px; display: block; }}
        .loading {{ text-align: center; font-size: 12px; color: #0088cc; display: none; margin-top: 4px; }}
    </style>
</head>
<body>

    <!-- RO'YXATDAN O'TISH SAHIFASI -->
    <div id="registerScreen" class="tab-content">
        <div class="card">
            <h2>🚖 {t_reg}</h2>
            <form id="regForm">
                <label>{l_name}</label>
                <input type="text" id="reg_name" required placeholder="Sardor Rahimov">

                <label>{l_photo}</label>
                <input type="file" id="file_profile" accept="image/*" required onchange="uploadImage('file_profile', 'reg_profile_photo')">
                <input type="hidden" id="reg_profile_photo">
                <div id="loading_file_profile" class="loading">Yuklanmoqda...</div>

                <label>{l_phone}</label>
                <input type="tel" id="reg_phone" required placeholder="+998901234567">

                <label>{l_car}</label>
                <input type="text" id="reg_car_model" required placeholder="Gentra (Oq)">

                <label>{l_plate}</label>
                <input type="text" id="reg_car_plate" required placeholder="01 A 777 AA">

                <label>{l_car1}</label>
                <input type="file" id="file_car1" accept="image/*" required onchange="uploadImage('file_car1', 'reg_car_photo1')">
                <input type="hidden" id="reg_car_photo1">
                <div id="loading_file_car1" class="loading">Yuklanmoqda...</div>

                <button type="submit" id="submitBtn">{btn_reg}</button>
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
                
                <label><b>Mashina (Oldi ko'rinishi):</b></label>
                <img id="p_car1" class="car-big-img" src="" alt="Mashina">

                <button type="button" class="reset-btn" onclick="clearData()">{reset_btn}</button>
            </div>
        </div>

        <!-- 2-BO'LIM: YO'NALISH VA SOZLAMALAR -->
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

                    <label>{l_mode}</label>
                    <select id="set_work_mode">
                        <option value="{mode_1}">{mode_1}</option>
                        <option value="{mode_2}">{mode_2}</option>
                        <option value="{mode_3}">{mode_3}</option>
                        <option value="{mode_4}">{mode_4}</option>
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

        function initApp() {{
            let driverData = localStorage.getItem('safar_driver');
            if (driverData) {{
                try {{
                    let parsed = JSON.parse(driverData);
                    if (parsed && parsed.name) {{
                        showDashboard(parsed);
                        return;
                    }}
                }} catch(e) {{}}
            }}
            document.getElementById('registerScreen').classList.add('active');
            document.getElementById('dashboardApp').style.display = 'none';
        }}

        initApp();

        async function uploadImage(inputId, hiddenId) {{
            let fileInput = document.getElementById(inputId);
            let loadingEl = document.getElementById('loading_' + inputId);
            let file = fileInput.files[0];
            if (!file) return;

            let formData = new FormData();
            formData.append('file', file);

            loadingEl.style.display = 'block';

            try {{
                let response = await fetch('/upload', {{
                    method: 'POST',
                    body: formData
                }});
                let result = await response.json();
                if (result.url) {{
                    document.getElementById(hiddenId).value = result.url;
                    loadingEl.innerText = "✅ Yuklandi!";
                    loadingEl.style.color = "green";
                }} else {{
                    alert("Xatolik!");
                    loadingEl.style.display = 'none';
                }}
            }} catch (err) {{
                alert("Server bilan aloqa yo'q!");
                loadingEl.style.display = 'none';
            }}
        }}

        document.getElementById('regForm').addEventListener('submit', function(e) {{
            e.preventDefault();
            let pPhoto = document.getElementById('reg_profile_photo').value;
            let cPhoto1 = document.getElementById('reg_car_photo1').value;

            if (!pPhoto || !cPhoto1) {{
                alert("Iltimos, rasmlar yuklanishini kuting!");
                return;
            }}

            let data = {{
                name: document.getElementById('reg_name').value,
                profile_photo: pPhoto,
                phone: document.getElementById('reg_phone').value,
                car_model: document.getElementById('reg_car_model').value,
                car_plate: document.getElementById('reg_car_plate').value,
                car_photo1: cPhoto1,
                from_city: "Toshkent",
                to_city: "Buxoro",
                passengers_count: 4,
                work_mode: "{mode_1}",
                min_price: 50000,
                max_price: 150000,
                balance: 15000,
                lang: "{lang}"
            }};

            localStorage.setItem('safar_driver', JSON.stringify(data));
            tg.sendData(JSON.stringify(data));
            showDashboard(data);
        }});

        function showDashboard(data) {{
            document.getElementById('registerScreen').classList.remove('active');
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

            switchTab(1);
        }}

        function switchTab(tabNum) {{
            document.querySelectorAll('#dashboardApp .tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

            if(tabNum === 1) document.getElementById('tab1').classList.add('active');
            if(tabNum === 2) document.getElementById('tab2').classList.add('active');
            if(tabNum === 3) document.getElementById('tab3').classList.add('active');
            if(tabNum === 4) document.getElementById('tab4').classList.add('active');

            document.querySelectorAll('.nav-item')[tabNum - 1].classList.add('active');
        }}

        function clearData() {{
            if (confirm("Haqiqatan ham ma'lumotlarni o'chirib, noldan ro'yxatdan o'tmoqchimisiz?")) {{
                localStorage.removeItem('safar_driver');
                location.reload();
            }}
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
    return web.Response(text="Safar Taxi Bot ishlamoqda!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_home)
    app.router.add_get("/driver-app", handle_driver_app)
    app.router.add_post("/upload", handle_upload)
    app.router.add_static("/uploads", UPLOAD_DIR)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot va Mini App ishga tushdi...")
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
