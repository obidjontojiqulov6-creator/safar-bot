import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiohttp import web

# Tokenni Render muhitidan olamiz
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# /start buyrug'i uchun asosiy menyu tugmalari
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚕 Toshkent ➔ Andijon")
    builder.button(text="🚕 Andijon ➔ Toshkent")
    builder.button(text="📞 Operator bilan bog'lanish")
    builder.adjust(2, 1) # Tugmalar tartibi: ikkitadan va bittadan
    
    await message.answer(
        "Assalomu alaykum! Safar taksi xizmatiga xush kelibsiz.\n"
        "Buyurtma berish uchun quyidagi yo'nalishlardan birini tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Toshkent - Andijon yo'nalishi bosilganda
@dp.message(F.text == "🚕 Toshkent ➔ Andijon")
async def tish_and(message: types.Message):
    await message.answer(
        "✅ **Toshkent ➔ Andijon** yo'nalishini tanladingiz.\n\n"
        "Iltimos, o'zingizga qulay bo'lgan aloqa raqamingizni yuboring (masalan: `+998901234567` yoki 'Kontakt yuborish' tugmasi orqali):",
        parse_mode="Markdown"
    )

# Andijon - Toshkent yo'nalishi bosilganda
@dp.message(F.text == "🚕 Andijon ➔ Toshkent")
async def and_tosh(message: types.Message):
    await message.answer(
        "✅ **Andijon ➔ Toshkent** yo'nalishini tanladingiz.\n\n"
        "Iltimos, o'zingizga qulay bo'lgan aloqa raqamingizni yuboring:",
        parse_mode="Markdown"
    )

# Operator bilan bog'lanish bosilganda
@dp.message(F.text == "📞 Operator bilan bog'lanish")
async def contact_operator(message: types.Message):
    await message.answer(
        "📞 Operator bilan bog'lanish uchun:\n"
        "Admin: @Safar_Admin\n"
        "Telefon: +998 90 000-00-00"
    )

# Boshqa yozilgan matnlar uchun javob
@dp.message()
async def echo_text(message: types.Message):
    await message.answer("Iltimos, pastdagi tugmalardan birini tanlang yoki /start buyrug'ini bosing.")

# Render uchun veb-server
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
    await asyncio.gather(web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
