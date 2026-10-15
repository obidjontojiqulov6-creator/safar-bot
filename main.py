import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Bu yerga BotFather'dan olgan tokeningizni yozasiz
import os
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Assalomu alaykum! Safar taksi xizmati botiga xush kelibsiz.\n\n"
        "Buyurtma berish uchun yo'nalishni tanlang:"
    )

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
