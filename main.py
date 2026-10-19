import asyncio
import logging
import os
from threading import Thread
from flask import Flask

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)

# ==========================================
# 1. Render Port Muammosini Hal Qiluvchi Flask Server
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Safar Bot status: Active and Running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ==========================================
# 2. Telegram Bot Sozlamalari
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
MINI_APP_URL = os.environ.get("MINI_APP_URL", "https://telegram.org")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================
# 3. Klaviaturalar (Keyboards)
# ==========================================

# 1. Tilni tanlash
lang_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🇺🇿 O'zbekcha"), KeyboardButton(text="🇷🇺 Русский")]
    ],
    resize_keyboard=True
)

# 2. Asosiy rol menyusi
role_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Yo'lovchi"), KeyboardButton(text="🚖 Haydovchi kabineti")]
    ],
    resize_keyboard=True
)

# 3. Yo'lovchi menyusi
passenger_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚖 Taksi chaqirish"), KeyboardButton(text="📍 Lokatsiyamni yuborish", request_location=True)],
        [KeyboardButton(text="💰 Tariflar"), KeyboardButton(text="📞 Qo'llab-quvvatlash")],
        [KeyboardButton(text="🔙 Asosiy menyuga qaytish")]
    ],
    resize_keyboard=True
)

# 4. Haydovchi uchun Inline Mini App va menyu
driver_inline_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📱 Haydovchi Mini App ochish",
                web_app=WebAppInfo(url=MINI_APP_URL)
            )
        ]
    ]
)

driver_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Mini App ochish")],
        [KeyboardButton(text="📋 Shartlar"), KeyboardButton(text="📞 Operator bilan bog'lanish")],
        [KeyboardButton(text="🔙 Asosiy menyuga qaytish")]
    ],
    resize_keyboard=True
)

# ==========================================
# 4. Xabarlar va Buyruqlar (Handlers)
# ==========================================

# /start buyrug'i
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    welcome_text = (
        "🇷🇺 Здравствуйте! Добро пожаловать в службу такси Safar. Пожалуйста, выберите язык:\n\n"
        "🇺🇿 Assalomu alaykum! Safar taksi xizmatiga xush kelibsiz. Iltimos, tilni tanlang:"
    )
    await message.answer(welcome_text, reply_markup=lang_keyboard)

# Til tanlanganda
@dp.message(F.text.in_(["🇺🇿 O'zbekcha", "🇷🇺 Русский"]))
async def select_language(message: types.Message):
    if message.text == "🇺🇿 O'zbekcha":
        text = "Siz kimsiz? Iltimos, o'z rolingizni tanlang:"
    else:
        text = "Кто вы? Пожалуйста, выберите свою роль:"
        
    await message.answer(text, reply_markup=role_keyboard)

# Yo'lovchi bo'limi
@dp.message(F.text == "👤 Yo'lovchi")
async def passenger_cabinet(message: types.Message):
    text = (
        "👤 **Yo'lovchi bo'limi**\n\n"
        "Kerakli xizmatni tanlang yoki geolokatsiyangizni yuboring:"
    )
    await message.answer(text, reply_markup=passenger_keyboard, parse_mode="Markdown")

# Yo'lovchi: Taksi chaqirish
@dp.message(F.text == "🚖 Taksi chaqirish")
async def order_taxi(message: types.Message):
    await message.answer(
        "Taksi buyurtma qilish uchun pastdagi **📍 Lokatsiyamni yuborish** tugmasini bosing yoki manzilingizni yozib yuboring:",
        parse_mode="Markdown"
    )

# Yo'lovchi: Lokatsiya kelganda
@dp.message(F.location)
async def handle_location(message: types.Message):
    lat = message.location.latitude
    lon = message.location.longitude
    await message.answer(
        f"📍 Joylashuvingiz qabul qilindi!\n\n"
        f"Yaqin atrofdagi haydovchilar qidirilmoqda...",
        reply_markup=passenger_keyboard
    )

# Yo'lovchi: Tariflar
@dp.message(F.text == "💰 Tariflar")
async def show_tariffs(message: types.Message):
    tariffs_text = (
        "💰 **Safar Taksi Tariflari:**\n\n"
        "🚘 **Ekonim:** Boshlang'ich 5,000 so'm (1 km = 1,800 so'm)\n"
        "Comfort:** Boshlang'ich 8,000 so'm (1 km = 2,500 so'm)\n"
        "🚚 **Yuk tashish:** Boshlang'ich 25,000 so'm"
    )
    await message.answer(tariffs_text, parse_mode="Markdown")

# Haydovchi bo'limi
@dp.message(F.text == "🚖 Haydovchi kabineti")
async def driver_cabinet(message: types.Message):
    text = (
        "🚖 **Haydovchi kabineti (Mini App)**\n\n"
        "Ro'yxatdan o'tish, buyurtmalarni ko'rish va anketa to'ldirish uchun pastdagi tugmani bosing:"
    )
    await message.answer(text, reply_markup=driver_inline_kb)
    await message.answer("Qo'shimcha imkoniyatlar:", reply_markup=driver_keyboard)

# Asosiy menyuga qaytish
@dp.message(F.text == "🔙 Asosiy menyuga qaytish")
async def back_to_main(message: types.Message):
    await message.answer("Asosiy menyuga qaytdingiz. Rolni tanlang:", reply_markup=role_keyboard)

# Qo'llab-quvvatlash / Operator
@dp.message(F.text.in_(["📞 Qo'llab-quvvatlash", "📞 Operator bilan bog'lanish"]))
async def support_handler(message: types.Message):
    await message.answer("📞 Bizning aloqa markazimiz: +998 (90) 123-45-67\nYoki admin: @safar_support")

# Boshqa matnli xabarlar
@dp.message()
async def default_handler(message: types.Message):
    await message.answer("Iltimos, pastdagi menyu tugmalaridan birini tanlang.", reply_markup=role_keyboard)

# ==========================================
# 5. Ishga tushirish
# ==========================================
async def main():
    keep_alive()
    print("Safar Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
