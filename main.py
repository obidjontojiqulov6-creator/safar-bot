import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web

# Tokenni Render muhitidan olamiz
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Assalomu alaykum! Safar taksi xizmatiga xush kelibsiz.\n"
        "Buyurtma berish uchun yo'nalishni tanlang:"
    )

# Render port talab qilgani uchun kichik veb-server ochamiz
async def handle(request):
    return web.Response(text="Bot ishlayapti!")

async def web_server():
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot ishga tushdi...")
    # Veb-server va Telegram botni bir vaqtning o'zida yurgizamiz
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
