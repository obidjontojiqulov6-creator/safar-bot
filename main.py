import asyncio
import logging
import os
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

# 1. Render talab qiladigan Veb-Server (Port muammosini hal qilish uchun)
app = Flask(__name__)

@app.route('/')
def home():
    return "Safar Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# 2. Telegram Bot sozlamalari
# Bot tokenini Render Environment Variables'dan oladi yoki shu yerga to'g'ridan-to'g'ri yozishingiz mumkin
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# /start buyrug'i uchun handler
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer("Assalomu alaykum! Safar Bot ishga tushdi va xizmatingizda.")

# Oddiy matnli xabarlarga javob qaytarish
@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"Siz yubordingiz: {message.text}")

# 3. Asosiy ishga tushirish funksiyasi
async def main():
    # Veb-serverni orqa fonda ishga tushiramiz
    keep_alive()
    
    # Telegram bot polling'ini boshlaymiz
    print("Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
