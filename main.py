import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

class BookingState(StatesGroup):
    waiting_for_lang = State()
    waiting_for_from_city = State()
    waiting_for_to_city = State()
    waiting_for_passengers = State()
    waiting_for_price = State()
    waiting_for_contact = State()

CITIES = [
    "Toshkent", "Andijon", "Buxoro", "Jizzax", 
    "Navoiy", "Namangan", "Qarshi", "Samarqand", 
    "Guliston", "Termiz", "Urganch", "Nukus"
]

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BookingState.waiting_for_lang)
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha")
    builder.button(text="🇷🇺 Русский")
    builder.adjust(2)
    
    await message.answer(
        "Assalomu alaykum! Safar taksi xizmatiga xush kelibsiz.\n"
        "Tilni tanlang / Пожалуйста, выберите язык:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.message(BookingState.waiting_for_lang, F.text.in_(["🇺🇿 O'zbekcha", "🇷🇺 Русский"]))
async def select_language(message: types.Message, state: FSMContext):
    lang = "uz" if "O'zbekcha" in message.text else "ru"
    await state.update_data(lang=lang)
    await state.set_state(BookingState.waiting_for_from_city)

    builder = ReplyKeyboardBuilder()
    for city in CITIES:
        builder.button(text=city)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(2, 2, 2, 2, 2, 2, 1)

    text = "📍 Qayerdan jo'naysiz? Hududni tanlang:" if lang == "uz" else "📍 Откуда выезжаете? Выберите регион:"
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_from_city)
async def select_from_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        return await cmd_start(message, state)
    
    if message.text not in CITIES:
        err = "Iltimos, tugmalardagi hududlardan birini tanlang." if lang == "uz" else "Пожалуйста, выберите регион с помощью кнопок."
        return await message.answer(err)

    await state.update_data(from_city=message.text)
    await state.set_state(BookingState.waiting_for_to_city)

    builder = ReplyKeyboardBuilder()
    for city in CITIES:
        if city != message.text:
            builder.button(text=city)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(2, 2, 2, 2, 2, 2, 1)

    text = f"🏁 Qayerga borasiz? (Jo'nash: {message.text})" if lang == "uz" else f"🏁 Куда едем? (Откуда: {message.text})"
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_to_city)
async def select_to_city(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_from_city)
        builder = ReplyKeyboardBuilder()
        for city in CITIES:
            if city != data.get("from_city"):
                builder.button(text=city)
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(2, 2, 2, 2, 2, 2, 1)
        text = "📍 Qayerdan jo'naysiz? Hududni tanlang:" if lang == "uz" else "📍 Откуда выезжаете? Выберите регион:"
        return await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

    if message.text not in CITIES:
        err = "Iltimos, ro'yxatdagi hududlardan birini tanlang." if lang == "uz" else "Пожалуйста, выберите регион из списка."
        return await message.answer(err)

    await state.update_data(to_city=message.text, passengers=[])
    await state.set_state(BookingState.waiting_for_passengers)

    await show_passenger_menu(message, [], lang)

async def show_passenger_menu(message: types.Message, passengers: list, lang: str):
    builder = ReplyKeyboardBuilder()
    builder.button(text="👨 Erkak" if lang == "uz" else "👨 Мужчина")
    builder.button(text="👩 Ayol" if lang == "uz" else "👩 Женщина")
    builder.button(text="🔄 Tozalash" if lang == "uz" else "🔄 Очистить")
    builder.button(text="➡️ Keyingi bo'lim" if lang == "uz" else "➡️ Следующий раздел")
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(2, 2, 1)

    pass_str = " ".join(passengers) if passengers else ("(Hali tanlanmadi)" if lang == "uz" else "(Еще не выбрано)")
    text = (
        f"👥 Yo'lovchilar tarkibini tanlang (Maksimal 4 ta):\nJoriy: {pass_str}"
        if lang == "uz" else
        f"👥 Выберите состав пассажиров (Максимум 4):\nТекущие: {pass_str}"
    )
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_passengers)
async def handle_passengers(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    passengers = data.get("passengers", [])

    text = message.text

    if text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_to_city)
        builder = ReplyKeyboardBuilder()
        for city in CITIES:
            if city != data.get("from_city"):
                builder.button(text=city)
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(2, 2, 2, 2, 2, 2, 1)
        return await message.answer("🏁 Qayerga borasiz?", reply_markup=builder.as_markup(resize_keyboard=True))

    if text in ["🔄 Tozalash", "🔄 Очистить"]:
        passengers = []
        await state.update_data(passengers=passengers)
        return await show_passenger_menu(message, passengers, lang)

    if text in ["➡️ Keyingi bo'lim", "➡️ Следующий раздел"]:
        if not passengers:
            err = "Iltimos, kamida 1 ta yo'lovchini tanlang!" if lang == "uz" else "Пожалуйста, выберите хотя бы 1 пассажира!"
            return await message.answer(err)
        
        await state.set_state(BookingState.waiting_for_price)
        builder = ReplyKeyboardBuilder()
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        builder.adjust(1)
        
        price_text = (
            "💵 Yo'lkira uchun bermoqchi bo'lgan summangizni kiriting (masalan: `50000` so'm):"
            if lang == "uz" else
            "💵 Введите сумму, которую готовы предложить за поездку (например: `50000` сум):"
        )
        return await message.answer(price_text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

    if text in ["👨 Erkak", "👨 Мужчина", "👩 Ayol", "👩 Женщина"]:
        if len(passengers) >= 4:
            warn = "Maksimal 4 ta yo'lovchi tanlash mumkin!" if lang == "uz" else "Максимум можно выбрать 4 пассажиров!"
            return await message.answer(warn)
        
        emoji = "👨" if "Erkak" in text or "Мужчина" in text else "👩"
        passengers.append(emoji)
        await state.update_data(passengers=passengers)
        return await show_passenger_menu(message, passengers, lang)
    
    await message.answer("Iltimos, pastdagi tugmalardan foydalaning.")

@dp.message(BookingState.waiting_for_price)
async def enter_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_passengers)
        return await show_passenger_menu(message, data.get("passengers", []), lang)

    await state.update_data(price=message.text)
    await state.set_state(BookingState.waiting_for_contact)

    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Kontaktni yuborish" if lang == "uz" else "📱 Отправить контакт", request_contact=True)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(1, 1)

    text = (
        "📞 Iltimos, aloqa uchun pastdagi **'📱 Kontaktni yuborish'** tugmasini bosing:"
        if lang == "uz" else
        "📞 Пожалуйста, нажмите кнопку **'📱 Отправить контакт'** ниже:"
    )
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(BookingState.waiting_for_contact, F.contact)
async def get_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    phone = message.contact.phone_number
    name = message.from_user.first_name
    pass_summary = " ".join(data.get('passengers', []))

    if lang == "uz":
        response_text = (
            f"Rahmat, {name}! Buyurtmangiz qabul qilindi ✅\n\n"
            f"📋 **Buyurtma tafsilotlari:**\n"
            f"📍 Qayerdan: {data.get('from_city')}\n"
            f"🏁 Qayerga: {data.get('to_city')}\n"
            f"👥 Odamlar: {pass_summary}\n"
            f"💵 Taklif qilingan narx: {data.get('price')}\n"
            f"📞 Tel raqam: `+{phone}`\n\n"
            "Tez orada haydovchilarimiz siz bilan bog'lanishadi."
        )
        cancel_btn_text = "❌ Buyurtmani bekor qilish / Qaytadan"
    else:
        response_text = (
            f"Спасибо, {name}! Ваш заказ принят ✅\n\n"
            f"📋 **Детали заказа:**\n"
            f"📍 Откуда: {data.get('from_city')}\n"
            f"🏁 Куда: {data.get('to_city')}\n"
            f"👥 Пассажиры: {pass_summary}\n"
            f"💵 Предложенная цена: {data.get('price')}\n"
            f"📞 Телефон: `+{phone}`\n\n"
            "Скоро наши водители свяжутся с вами."
        )
        cancel_btn_text = "❌ Отменить заказ / Заново"

    inline_builder = InlineKeyboardBuilder()
    inline_builder.button(text=cancel_btn_text, callback_data="cancel_order")

    await message.answer(response_text, reply_markup=inline_builder.as_markup(), parse_mode="Markdown")
    await state.clear()

@dp.callback_query(F.data == "cancel_order")
async def cancel_order_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Buyurtma bekor qilindi!")
    
    # Tilni saqlab qolgan holda shaharni tanlash qismiga qaytaramiz
    await state.set_state(BookingState.waiting_for_from_city)
    
    # Agar til ma'lumoti saqlanmagan bo'lsa default o'zbekcha olamiz
    lang = "uz"

    builder = ReplyKeyboardBuilder()
    for city in CITIES:
        builder.button(text=city)
    builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
    builder.adjust(2, 2, 2, 2, 2, 2, 1)

    text = "❌ Buyurtma bekor qilindi.\n\n📍 Qayerdan jo'naysiz? Hududni tanlang:" if lang == "uz" else "❌ Заказ отменен.\n\n📍 Откуда выезжаете? Выберите регион:"
    
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await callback.message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(BookingState.waiting_for_contact)
async def wrong_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text in ["🔙 Orqaga", "🔙 Назад"]:
        await state.set_state(BookingState.waiting_for_price)
        builder = ReplyKeyboardBuilder()
        builder.button(text="🔙 Orqaga" if lang == "uz" else "🔙 Назад")
        return await message.answer("💵 Summani qaytadan kiriting:", reply_markup=builder.as_markup(resize_keyboard=True))

    err = (
        "⚠️ Iltimos, qo'lda raqam yozmang, faqat pastdagi '📱 Kontaktni yuborish' tugmasini bosing!"
        if lang == "uz" else
        "⚠️ Пожалуйста, не пишите номер вручную, нажмите кнопку '📱 Отправить контакт' ниже!"
    )
    await message.answer(err)

@dp.message()
async def echo_text(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

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

If __name__ == "__main__":
    asyncio.run(main())
