import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

ORDERS = {}       
DRIVERS = {}      
CITIES = ["Toshkent", "Andijon", "Buxoro", "Jizzax", "Navoiy", "Namangan", "Qarshi", "Samarqand", "Guliston", "Termiz", "Urganch", "Nukus"]

class RegState(StatesGroup):
    lang = State()
    role = State()
    name = State()
    phone = State()
    car = State()
    photo = State()
    current_city = State()
    target_city = State()
    passenger_from = State()
    passenger_to = State()
    passenger_price = State()
    passenger_contact = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(RegState.lang)
    builder = ReplyKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha")
    builder.button(text="🇷🇺 Русский")
    builder.adjust(2)
    await message.answer("Tilni tanlang / Выберите язык:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(RegState.lang)
async def set_lang(message: types.Message, state: FSMContext):
    lang = "uz" if "O'zbekcha" in message.text else "ru"
    await state.update_data(lang=lang)
    await state.set_state(RegState.role)
    
    builder = ReplyKeyboardBuilder()
    if lang == "uz":
        builder.button(text="👤 Yo'lovchi")
        builder.button(text="🚖 Haydovchi")
        text = "Siz kimsiz?"
    else:
        builder.button(text="👤 Пассажир")
        builder.button(text="🚖 Водитель")
        text = "Кто вы?"
    builder.adjust(2)
    await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(RegState.role)
async def set_role(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    text = message.text

    if text in ["👤 Yo'lovchi", "👤 Пассажир"]:
        await state.set_state(RegState.passenger_from)
        builder = ReplyKeyboardBuilder()
        for c in CITIES: builder.button(text=c)
        builder.adjust(2, 2, 2, 2, 2, 2)
        return await message.answer("📍 Qayerdan jo'naysiz?" if lang=="uz" else "📍 Откуда?", reply_markup=builder.as_markup(resize_keyboard=True))

    elif text in ["🚖 Haydovchi", "🚖 Водитель"]:
        driver_id = message.from_user.id
        if driver_id not in DRIVERS:
            await state.set_state(RegState.name)
            return await message.answer("📝 Ism va Familiyangizni kiriting:" if lang=="uz" else "📝 Введите Имя и Фамилию:", reply_markup=types.ReplyKeyboardRemove())
        else:
            return await show_driver_menu(message)

# --- HAYDOVCHI RO'YXATDAN O'TISH ---
@dp.message(RegState.name)
async def dr_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(RegState.phone)
    lang = (await state.get_data()).get("lang", "uz")
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Telefon raqamni yuborish" if lang=="uz" else "📱 Отправить номер", request_contact=True)
    await message.answer("📞 Telefon raqamingizni yuboring:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(RegState.phone, F.contact)
async def dr_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await state.set_state(RegState.car)
    await message.answer("🚗 Mashina rusumi va raqami (masalan: Cobalt 01 A 777 AA):", reply_markup=types.ReplyKeyboardRemove())

@dp.message(RegState.car)
async def dr_car(message: types.Message, state: FSMContext):
    await state.update_data(car=message.text)
    await state.set_state(RegState.photo)
    await message.answer("📸 Mashinangizning rasmini yuboring:")

@dp.message(RegState.photo, F.photo)
async def dr_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(RegState.current_city)
    builder = ReplyKeyboardBuilder()
    for c in CITIES: builder.button(text=c)
    builder.adjust(2, 2, 2, 2, 2, 2)
    await message.answer("📍 Hozir qaysi shahardasiz?", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(RegState.current_city)
async def dr_cur_city(message: types.Message, state: FSMContext):
    if message.text not in CITIES: return await message.answer("Shaharni tugmadan tanlang.")
    await state.update_data(current_city=message.text)
    await state.set_state(RegState.target_city)
    builder = ReplyKeyboardBuilder()
    for c in CITIES: 
        if c != message.text: builder.button(text=c)
    builder.adjust(2, 2, 2, 2, 2, 2)
    await message.answer("🏁 Qaysi shaharga borasiz?", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(RegState.target_city)
async def dr_tar_city(message: types.Message, state: FSMContext):
    if message.text not in CITIES: return await message.answer("Shaharni tugmadan tanlang.")
    data = await state.get_data()
    driver_id = message.from_user.id
    
    DRIVERS[driver_id] = {
        "name": data.get("name"),
        "phone": data.get("phone"),
        "car": data.get("car"),
        "photo": data.get("photo"),
        "current_city": data.get("current_city"),
        "target_city": message.text,
        "balance": 10000,
        "lang": data.get("lang", "uz")
    }
    await state.clear()
    await message.answer("✅ Ro'yxatdan muvaffaqiyatli o'tdingiz!")
    await show_driver_menu(message)

async def show_driver_menu(message: types.Message):
    driver_id = message.from_user.id
    d = DRIVERS[driver_id]
    lang = d.get("lang", "uz")
    
    builder = ReplyKeyboardBuilder()
    if lang == "uz":
        builder.button(text="📋 Mos buyurtmalar")
        builder.button(text="💰 Balans")
        builder.button(text="🏠 Asosiy menyu")
        text = f"🚖 **Haydovchi kabineti**\n\n👤 Ism: {d['name']}\n🚗 Mashina: {d['car']}\n📍 Yo'nalish: {d['current_city']} ➔ {d['target_city']}\n💳 Balans: {d['balance']} so'm"
    else:
        builder.button(text="📋 Подходящие заказы")
        builder.button(text="💰 Баланс")
        builder.button(text="🏠 Главное меню")
        text = f"🚖 **Кабинет водителя**\n\n👤 Имя: {d['name']}\n🚗 Машина: {d['car']}\n📍 Маршрут: {d['current_city']} ➔ {d['target_city']}\n💳 Баланс: {d['balance']} сум"
    builder.adjust(2, 1)

    if d.get("photo"):
        await message.answer_photo(d["photo"], caption=text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=builder.as_markup(resize_keyboard=True), parse_mode="Markdown")

@dp.message(F.text.in_(["🏠 Asosiy menyu", "🏠 Главное меню"]))
async def back_home(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

@dp.message(F.text.in_(["💰 Balans", "💰 Баланс"]))
async def check_bal(message: types.Message):
    d = DRIVERS.get(message.from_user.id)
    if d: await message.answer(f"Sizning balansingiz: {d['balance']} so'm")

# --- YO'LOVCHI QISMI ---
@dp.message(RegState.passenger_from)
async def p_from(message: types.Message, state: FSMContext):
    if message.text not in CITIES: return
    await state.update_data(p_from=message.text)
    await state.set_state(RegState.passenger_to)
    builder = ReplyKeyboardBuilder()
    for c in CITIES: 
        if c != message.text: builder.button(text=c)
    builder.adjust(2, 2, 2, 2, 2, 2)
    await message.answer("🏁 Qayerga borasiz?", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(RegState.passenger_to)
async def p_to(message: types.Message, state: FSMContext):
    if message.text not in CITIES: return
    await state.update_data(p_to=message.text)
    await state.set_state(RegState.passenger_price)
    await message.answer("💵 Beradigan pulingizni yozing (masalan: 50000 so'm):", reply_markup=types.ReplyKeyboardRemove())

@dp.message(RegState.passenger_price)
async def p_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await state.set_state(RegState.passenger_contact)
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Tel raqamni yuborish", request_contact=True)
    await message.answer("📞 Telefon raqamingizni yuboring:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(RegState.passenger_contact, F.contact)
async def p_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    oid = str(len(ORDERS) + 1)
    ORDERS[oid] = {
        "name": message.from_user.first_name,
        "from_city": data.get("p_from"),
        "to_city": data.get("p_to"),
        "price": data.get("price"),
        "phone": message.contact.phone_number
    }
    await state.clear()
    await message.answer("✅ Buyurtmangiz qabul qilindi!")
    
    for did, drv in DRIVERS.items():
        if drv['current_city'] == ORDERS[oid]['from_city'] and drv['target_city'] == ORDERS[oid]['to_city']:
            kb = InlineKeyboardBuilder()
            kb.button(text="📞 Kontaktni ochish (2000 so'm)", callback_data=f"get_{oid}")
            await bot.send_message(did, f"🔔 Yangi buyurtma!\n{ ORDERS[oid]['from_city'] } ➔ { ORDERS[oid]['to_city'] }\nNarx: { ORDERS[oid]['price'] }", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("get_"))
async def get_order(call: types.CallbackQuery):
    did = call.from_user.id
    oid = call.data.split("_")[1]
    if did in DRIVERS and DRIVERS[did]['balance'] >= 2000:
        DRIVERS[did]['balance'] -= 2000
        ord_info = ORDERS[oid]
        await call.message.answer(f"📞 Yo'lovchi: {ord_info['name']}\nTel: +{ord_info['phone']}")
        await call.answer()
    else:
        await call.answer("Balans yetarli emas!", show_alert=True)

@dp.message()
async def fallback(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
