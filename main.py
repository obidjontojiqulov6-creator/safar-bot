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
# Tokenni Render Environment Variables'dan oladi
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# Mini App URL (Agar o'zingizning veb-saytingiz/Mini App'ingiz bo'lsa shuni yozing)
MINI_APP_URL = os.environ.get("MINI_APP_URL", "https://telegram.org")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==========================================
# 3. Klaviaturalar (Keyboards)
# ==========================================

# 1-Sakkiz: Tilni tanlash klaviaturasi
lang_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🇺🇿 O'zbekcha"), KeyboardButton(text="🇷🇺 Русский")]
    ],
    resize_keyboard=True
)

# 2-Sakkiz: Rolni tanlash (Asosiy menyu)
role_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Yo'lovchi"), KeyboardButton(text="🚖 Haydovchi kabineti")]
    ],
    resize_keyboard=True
)

# 3-Sakkiz: Haydovchi uchun Inline Mini App tugmasi
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

# ==========================================
# 4. Xabarlar va Buyruqlar (Handlers)
# ==========================================

# /start buyrug'i kelganda
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

# Haydovchi kabineti tanlanganda
@dp.message(F.text == "🚖 Haydovchi kabineti")
async def driver_cabinet(message: types.Message):
    text = (
        "🚖 Haydovchi kabineti (Mini App)\n\n"
        "Ro'yxatdan o'tish va anketa to'ldirish uchun pastdagi tugmani bosing:"
    )
    await message.answer(text, reply_markup=driver_inline_kb)

# Yo'lovchi bo'limi tanlanganda
@dp.message(F.text == "👤 Yo'lovchi")
async def passenger_cabinet(message: types.Message):
    text = (
        "👤 Yo'lovchi bo'limiga xush kelibsiz!\n\n"
        "Taksi buyurtma qilish uchun joylashuvingizni yuboring yoki kerakli xizmatni tanlang."
    )
    await message.answer(text, reply_markup=role_keyboard)

# Boshqa har qanday xabar uchun (Noma'lum buyruqlar)
@dp.message()
async def default_handler(message: types.Message):
    await message.answer("Iltimos, pastdagi menyu tugmalaridan birini tanlang.", reply_markup=role_keyboard)

# ==========================================
# 5. Ishga tushirish (Main Loop)
# ==========================================
async def main():
    # Render uchun Flask veb-serverini orqa fonda yurgizamiz
    keep_alive()
    
    print("Safar Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
