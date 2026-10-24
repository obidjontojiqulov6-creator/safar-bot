import asyncio
import logging
import os
import re

import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
    Message, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from aiohttp import web

logging.basicConfig(level=logging.INFO)

# Render -> Environment bo'limida shu 2 ta o'zgaruvchini kiriting
BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
PORT = int(os.environ.get("PORT", 10000))

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
pool: asyncpg.Pool | None = None


class Order(StatesGroup):
    step = State()


START_TEXT = (
    "👋 Assalomu alaykum! / Здравствуйте!\n\n"
    "🚕 Safar Taxi: O'zbekiston bo'ylab taksi va dostavkani oson toping.\n"
    "🚕 Safar Taxi: легко находите такси и доставку по всему Узбекистану.\n\n"
    "Tilni tanlang / Выберите язык:"
)

T = {
    "uz": {
        "type": "Xizmat turini tanlang:", "p": "🚕 Yo'lovchi", "d": "📦 Dostavka",
        "from": "📍 Qayerdan yo'lga chiqasiz? (viloyat/shahar/tuman)",
        "to": "🏁 Qayerga borasiz?",
        "people": "👥 Necha kishi ketasiz? (raqam kiriting)",
        "comment": "📝 Izoh yozing (yo'q bo'lsa «-» yuboring):",
        "price": "💰 Yo'l kira uchun qancha bermoqchisiz? (so'mda, raqam)",
        "pickup": "📌 Sizni qayerdan olib ketishsin? Manzilni yozing:",
        "phone": "📞 Bog'lanish uchun telefon raqamingiz (+998...) yoki tugmani bosing:",
        "share": "📱 Raqamni yuborish",
        "order": "✅ Buyurtma berish", "cancel": "❌ Bekor qilish",
        "bad_num": "❗ Faqat raqam kiriting.", "bad_phone": "❗ Telefon noto'g'ri. Masalan: +998901234567",
        "done": "✅ Buyurtmangiz qabul qilindi! Tez orada haydovchi siz bilan bog'lanadi.",
        "cancelled": "Bekor qilindi. Qayta boshlash: /start",
        "title": "Buyurtmangizni tekshiring:",
        "labels": {"from": "Qayerdan", "to": "Qayerga", "people": "Kishi soni", "comment": "Izoh",
                   "price": "Yo'l kira", "pickup": "Olib ketish joyi", "phone": "Telefon"},
    },
    "oz": {
        "type": "Хизмат турини танланг:", "p": "🚕 Йўловчи", "d": "📦 Доставка",
        "from": "📍 Қаердан йўлга чиқасиз? (вилоят/шаҳар/туман)",
        "to": "🏁 Қаерга борасиз?",
        "people": "👥 Неча киши кетасиз? (рақам киритинг)",
        "comment": "📝 Изоҳ ёзинг (йўқ бўлса «-» юборинг):",
        "price": "💰 Йўл кира учун қанча бермоқчисиз? (сўмда, рақам)",
        "pickup": "📌 Сизни қаердан олиб кетишсин? Манзилни ёзинг:",
        "phone": "📞 Боғланиш учун телефон рақамингиз (+998...) ёки тугмани босинг:",
        "share": "📱 Рақамни юбориш",
        "order": "✅ Буюртма бериш", "cancel": "❌ Бекор қилиш",
        "bad_num": "❗ Фақат рақам киритинг.", "bad_phone": "❗ Телефон нотўғри. Масалан: +998901234567",
        "done": "✅ Буюртмангиз қабул қилинди! Тез орада ҳайдовчи сиз билан боғланади.",
        "cancelled": "Бекор қилинди. Қайта бошлаш: /start",
        "title": "Буюртмангизни текширинг:",
        "labels": {"from": "Қаердан", "to": "Қаерга", "people": "Киши сони", "comment": "Изоҳ",
                   "price": "Йўл кира", "pickup": "Олиб кетиш жойи", "phone": "Телефон"},
    },
    "ru": {
        "type": "Выберите тип услуги:", "p": "🚕 Пассажир", "d": "📦 Доставка",
        "from": "📍 Откуда выезжаете? (область/город/район)",
        "to": "🏁 Куда едете?",
        "people": "👥 Сколько человек поедет? (введите число)",
        "comment": "📝 Напишите комментарий (если нет, отправьте «-»):",
        "price": "💰 Сколько готовы заплатить за проезд? (в сумах, число)",
        "pickup": "📌 Откуда вас забрать? Напишите адрес:",
        "phone": "📞 Номер телефона для связи (+998...) или нажмите кнопку:",
        "share": "📱 Отправить номер",
        "order": "✅ Заказать", "cancel": "❌ Отменить",
        "bad_num": "❗ Введите только число.", "bad_phone": "❗ Неверный номер. Пример: +998901234567",
        "done": "✅ Ваш заказ принят! Водитель скоро свяжется с вами.",
        "cancelled": "Отменено. Начать заново: /start",
        "title": "Проверьте ваш заказ:",
        "labels": {"from": "Откуда", "to": "Куда", "people": "Кол-во человек", "comment": "Комментарий",
                   "price": "Цена", "pickup": "Место посадки", "phone": "Телефон"},
    },
}

STEPS_PASSENGER = ["from", "to", "people", "comment", "price", "pickup", "phone"]
STEPS_DELIVERY = ["from", "to", "comment", "price", "pickup", "phone"]


# ---------- Baza ----------
async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id SERIAL PRIMARY KEY,
            kind TEXT, from_city TEXT, to_city TEXT, people TEXT, comment TEXT,
            price BIGINT, pickup TEXT, phone TEXT,
            tg_id BIGINT, user_name TEXT,
            status TEXT DEFAULT 'open',
            created TIMESTAMPTZ DEFAULT NOW()
        )""")


# ---------- Yordamchi ----------
def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha (lotin)", callback_data="lang:uz")],
        [InlineKeyboardButton(text="🇺🇿 Ўзбекча (кирил)", callback_data="lang:oz")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")],
    ])


async def ask(m: Message, data: dict):
    t = T[data["lang"]]
    key = data["steps"][data["i"]]
    if key == "phone":
        markup = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=t["share"], request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True)
    else:
        markup = ReplyKeyboardRemove()
    await m.answer(t[key], reply_markup=markup)


def clean_phone(s: str) -> str | None:
    digits = re.sub(r"\D", "", s)
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    return None


# ---------- Handlerlar ----------
@dp.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(START_TEXT, reply_markup=lang_kb())


@dp.callback_query(F.data.startswith("lang:"))
async def choose_lang(c: CallbackQuery, state: FSMContext):
    lang = c.data.split(":")[1]
    await state.update_data(lang=lang)
    t = T[lang]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t["p"], callback_data="type:p"),
        InlineKeyboardButton(text=t["d"], callback_data="type:d"),
    ]])
    await c.message.answer(t["type"], reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("type:"))
async def choose_type(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "lang" not in data:
        await c.message.answer(START_TEXT, reply_markup=lang_kb())
        return await c.answer()
    kind = c.data.split(":")[1]
    steps = STEPS_PASSENGER if kind == "p" else STEPS_DELIVERY
    await state.update_data(kind=kind, steps=steps, i=0, answers={})
    await state.set_state(Order.step)
    await ask(c.message, await state.get_data())
    await c.answer()


@dp.message(Order.step, F.text | F.contact)
async def collect(m: Message, state: FSMContext):
    data = await state.get_data()
    t = T[data["lang"]]
    key = data["steps"][data["i"]]
    raw = m.contact.phone_number if m.contact else (m.text or "").strip()

    if key in ("people", "price"):
        digits = raw.replace(" ", "")
        if not digits.isdigit():
            return await m.answer(t["bad_num"])
        value = digits
    elif key == "phone":
        value = clean_phone(raw)
        if not value:
            return await m.answer(t["bad_phone"])
    else:
        value = raw[:300]

    answers = data["answers"]
    answers[key] = value
    i = data["i"] + 1
    await state.update_data(answers=answers, i=i)

    if i < len(data["steps"]):
        return await ask(m, await state.get_data())

    lines = [f"{t['labels'][k]}: {answers[k]}" for k in data["steps"]]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["order"], callback_data="confirm")],
        [InlineKeyboardButton(text=t["cancel"], callback_data="cancel")],
    ])
    await m.answer("👇", reply_markup=ReplyKeyboardRemove())
    await m.answer(f"{t['title']}\n\n" + "\n".join(lines), reply_markup=kb)


@dp.callback_query(F.data == "confirm")
async def confirm(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("answers") or data["i"] < len(data["steps"]):
        return await c.answer()
    t = T[data["lang"]]
    a = data["answers"]
    u = c.from_user
    await pool.execute(
        """INSERT INTO orders(kind, from_city, to_city, people, comment, price,
                              pickup, phone, tg_id, user_name)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
        data["kind"], a["from"], a["to"], a.get("people"), a["comment"],
        int(a["price"]), a["pickup"], a["phone"], u.id, u.full_name,
    )
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.answer(t["done"])
    await state.clear()
    await c.answer()


@dp.callback_query(F.data == "cancel")
async def cancel(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    t = T[data.get("lang", "uz")]
    await state.clear()
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.answer(t["cancelled"])
    await c.answer()


# ---------- Render uchun "tirik" server ----------
async def health(_):
    return web.Response(text="ok")


async def run_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()


async def main():
    await init_db()
    await run_web()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
