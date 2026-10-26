"""Safar Taxi: yo'lovchi va yuk yuboruvchilar boti (to'liq versiya).

Render -> Environment:  BOT_TOKEN, DATABASE_URL
requirements.txt:       aiogram==3.13.1, asyncpg, aiohttp
"""
import asyncio
import logging
import os

import aiohttp
import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton as IB, InlineKeyboardMarkup as IM,
    KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from aiohttp import web

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"].replace("&channel_binding=require", "")
PORT = int(os.environ.get("PORT", 10000))
SELF_URL = os.environ.get("RENDER_EXTERNAL_URL")  # Render o'zi beradi

MAX_PEOPLE = 4
REFUND_PERCENT = 70  # rad etilganda haydovchiga qaytariladigan ulush

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
pool: asyncpg.Pool | None = None
busy: set[int] = set()


class Flow(StatesGroup):
    s = State()


# ---------------------------------------------------------------- Viloyatlar
# (lotin, kirill, rus). Bazaga lotin nomi yoziladi.
REG = [
    ("Toshkent", "Тошкент", "Ташкент"),
    ("Nurafshon", "Нурафшон", "Нурафшон"),
    ("Andijon", "Андижон", "Андижан"),
    ("Buxoro", "Бухоро", "Бухара"),
    ("Farg'ona", "Фарғона", "Фергана"),
    ("Jizzax", "Жиззах", "Джизак"),
    ("Namangan", "Наманган", "Наманган"),
    ("Navoiy", "Навоий", "Навои"),
    ("Qarshi", "Қарши", "Карши"),
    ("Samarqand", "Самарқанд", "Самарканд"),
    ("Guliston", "Гулистон", "Гулистан"),
    ("Termiz", "Термиз", "Термез"),
    ("Urganch", "Урганч", "Ургенч"),
    ("Nukus", "Нукус", "Нукус"),
]
LI = {"uz": 0, "oz": 1, "ru": 2}


def reg(lang: str, idx: int) -> str:
    return REG[idx][LI[lang]]


# ---------------------------------------------------------------- Matnlar
START_TEXT = (
    "👋 Assalomu alaykum! / Здравствуйте!\n\n"
    "🚕 Safar Taxi: O'zbekiston bo'ylab taksi va yuk yuborishni oson toping.\n"
    "🚕 Safar Taxi: легко находите такси и отправку грузов по всему Узбекистану.\n\n"
    "Tilni tanlang / Выберите язык:"
)

T = {
    "uz": {
        "service": "Kim ekanligingizni tanlang:",
        "p": "🚕 Yo'lovchi", "c": "📦 Yuk yuboruvchi", "back": "⬅️ Ortga",
        "from_p": "📍 Qayerdan ketasiz?", "from_c": "📍 Yukni qayerdan yuborasiz?",
        "to_p": "🏁 Qayerga borasiz?", "to_c": "🏁 Yuk qayerga boradi?",
        "people": "👥 Necha kishi ketasiz?\nHar bir kishi uchun 👨 yoki 👩 tugmasini bir martadan bosing (ko'pi bilan {max} kishi).",
        "men": "👨 Erkak", "women": "👩 Ayol", "clear": "🔄 Tozalash", "next": "➡️ Davom etish",
        "people_now": "Tanlandi: 👨 {m} ta, 👩 {w} ta (jami {t}/{max})",
        "max": "Ko'pi bilan {max} kishi!", "need_one": "Kamida 1 kishini tanlang!",
        "weight": "⚖️ Yukning og'irligini kiriting (kg, raqam bilan):",
        "price_p": "💰 Yo'l kira uchun qancha to'lay olasiz? (so'mda, raqam bilan)",
        "price_c": "💰 Yuk yuborish uchun qancha to'lay olasiz? (so'mda, raqam bilan)",
        "comment_p": "📝 Izoh yozing: yukingiz bormi, chaqaloq, boshqa talablar...",
        "comment_c": "📝 Yuk haqida ma'lumot yozing (nima yuk, o'lchami, qanday ehtiyot bo'lish kerak...)",
        "skip": "⏭ O'tkazib yuborish",
        "pickup_p": "📌 Sizni qayerdan olib ketishsin? Manzilni yozib kiriting:",
        "pickup_c": "📌 Yukni qayerdan olib ketishsin? Manzilni yozib kiriting:",
        "phone": "📞 Bog'lanish uchun telefon raqamingizni yuboring. Pastdagi tugmani bosing (Telegram qaysi raqamga ochilgan bo'lsa, shu raqam yuboriladi):",
        "share": "📱 Raqamni yuborish",
        "bad_num": "❗ Faqat raqam kiriting.",
        "own_phone": "❗ Faqat o'zingizning raqamingizni yuboring (pastdagi tugma orqali).",
        "use_btn": "❗ Iltimos, pastdagi tugmani bosing.",
        "use_inline": "👆 Iltimos, tugmalardan birini tanlang.",
        "check": "Ma'lumotlaringizni tekshiring:",
        "order": "✅ Buyurtma berish",
        "placed": "✅ Buyurtma №{id} qabul qilindi.\n⏳ Holati: jarayonda. Haydovchi topilishi bilan sizga xabar beramiz.",
        "cancel": "❌ Bekor qilish", "new": "➕ Yangi buyurtma",
        "cancelled": "❌ Buyurtma №{id} bekor qilindi.",
        "cant_cancel": "Bu buyurtmani bekor qilib bo'lmaydi: haydovchi topilgan. Uning ma'lumotlarini ko'rib, qabul qiling yoki rad eting.",
        "drv": "🚖 Buyurtma №{id} uchun haydovchi topildi!",
        "accept": "✅ Qabul qilish", "reject": "❌ Rad etish",
        "accepted": "✅ Ajoyib! Haydovchi bilan telefon orqali bog'laning. Yo'lingiz bexatar bo'lsin! 🚕",
        "rejected": "Haydovchi rad etildi. Buyurtma №{id} yana jarayonda ⏳",
        "error": "⚠️ Xatolik yuz berdi, birozdan keyin qayta urinib ko'ring.",
        "old": "Bu tugma eskirgan.", "cur": "so'm",
        "L": {"from": "Qayerdan", "to": "Qayerga", "people": "Kishi soni", "weight": "Og'irligi",
              "price": "Narx", "comment": "Izoh", "pickup": "Olib ketish joyi", "phone": "Telefon"},
        "D": {"name": "Ism familya", "birth": "Tug'ilgan sana", "phone": "Telefon",
              "num": "Avtomobil raqami", "car": "Rusumi va rangi"},
    },
    "oz": {
        "service": "Ким эканлигингизни танланг:",
        "p": "🚕 Йўловчи", "c": "📦 Юк юборувчи", "back": "⬅️ Орқага",
        "from_p": "📍 Қаердан кетасиз?", "from_c": "📍 Юкни қаердан юборасиз?",
        "to_p": "🏁 Қаерга борасиз?", "to_c": "🏁 Юк қаерга боради?",
        "people": "👥 Неча киши кетасиз?\nҲар бир киши учун 👨 ёки 👩 тугмасини бир мартадан босинг (кўпи билан {max} киши).",
        "men": "👨 Эркак", "women": "👩 Аёл", "clear": "🔄 Тозалаш", "next": "➡️ Давом этиш",
        "people_now": "Танланди: 👨 {m} та, 👩 {w} та (жами {t}/{max})",
        "max": "Кўпи билан {max} киши!", "need_one": "Камида 1 кишини танланг!",
        "weight": "⚖️ Юкнинг оғирлигини киритинг (кг, рақам билан):",
        "price_p": "💰 Йўл кира учун қанча тўлай оласиз? (сўмда, рақам билан)",
        "price_c": "💰 Юк юбориш учун қанча тўлай оласиз? (сўмда, рақам билан)",
        "comment_p": "📝 Изоҳ ёзинг: юкингиз борми, чақалоқ, бошқа талаблар...",
        "comment_c": "📝 Юк ҳақида маълумот ёзинг (нима юк, ўлчами, қандай эҳтиёт бўлиш керак...)",
        "skip": "⏭ Ўтказиб юбориш",
        "pickup_p": "📌 Сизни қаердан олиб кетишсин? Манзилни ёзиб киритинг:",
        "pickup_c": "📌 Юкни қаердан олиб кетишсин? Манзилни ёзиб киритинг:",
        "phone": "📞 Боғланиш учун телефон рақамингизни юборинг. Пастдаги тугмани босинг (Telegram қайси рақамга очилган бўлса, шу рақам юборилади):",
        "share": "📱 Рақамни юбориш",
        "bad_num": "❗ Фақат рақам киритинг.",
        "own_phone": "❗ Фақат ўзингизнинг рақамингизни юборинг (пастдаги тугма орқали).",
        "use_btn": "❗ Илтимос, пастдаги тугмани босинг.",
        "use_inline": "👆 Илтимос, тугмалардан бирини танланг.",
        "check": "Маълумотларингизни текширинг:",
        "order": "✅ Буюртма бериш",
        "placed": "✅ Буюртма №{id} қабул қилинди.\n⏳ Ҳолати: жараёнда. Ҳайдовчи топилиши билан сизга хабар берамиз.",
        "cancel": "❌ Бекор қилиш", "new": "➕ Янги буюртма",
        "cancelled": "❌ Буюртма №{id} бекор қилинди.",
        "cant_cancel": "Бу буюртмани бекор қилиб бўлмайди: ҳайдовчи топилган. Унинг маълумотларини кўриб, қабул қилинг ёки рад этинг.",
        "drv": "🚖 Буюртма №{id} учун ҳайдовчи топилди!",
        "accept": "✅ Қабул қилиш", "reject": "❌ Рад этиш",
        "accepted": "✅ Ажойиб! Ҳайдовчи билан телефон орқали боғланинг. Йўлингиз бехатар бўлсин! 🚕",
        "rejected": "Ҳайдовчи рад этилди. Буюртма №{id} яна жараёнда ⏳",
        "error": "⚠️ Хатолик юз берди, бироздан кейин қайта уриниб кўринг.",
        "old": "Бу тугма эскирган.", "cur": "сўм",
        "L": {"from": "Қаердан", "to": "Қаерга", "people": "Киши сони", "weight": "Оғирлиги",
              "price": "Нарх", "comment": "Изоҳ", "pickup": "Олиб кетиш жойи", "phone": "Телефон"},
        "D": {"name": "Исм фамилия", "birth": "Туғилган сана", "phone": "Телефон",
              "num": "Автомобил рақами", "car": "Русуми ва ранги"},
    },
    "ru": {
        "service": "Выберите, кто вы:",
        "p": "🚕 Пассажир", "c": "📦 Отправитель груза", "back": "⬅️ Назад",
        "from_p": "📍 Откуда выезжаете?", "from_c": "📍 Откуда отправляете груз?",
        "to_p": "🏁 Куда едете?", "to_c": "🏁 Куда отправляется груз?",
        "people": "👥 Сколько человек поедет?\nНажмите 👨 или 👩 по одному разу за каждого человека (не более {max}).",
        "men": "👨 Мужчина", "women": "👩 Женщина", "clear": "🔄 Сбросить", "next": "➡️ Продолжить",
        "people_now": "Выбрано: 👨 {m}, 👩 {w} (всего {t}/{max})",
        "max": "Не более {max} человек!", "need_one": "Выберите хотя бы 1 человека!",
        "weight": "⚖️ Введите вес груза (кг, числом):",
        "price_p": "💰 Сколько вы готовы заплатить за проезд? (в сумах, числом)",
        "price_c": "💰 Сколько вы готовы заплатить за отправку груза? (в сумах, числом)",
        "comment_p": "📝 Напишите комментарий: есть ли багаж, ребёнок, другие пожелания...",
        "comment_c": "📝 Напишите о грузе (что за груз, размер, как обращаться...)",
        "skip": "⏭ Пропустить",
        "pickup_p": "📌 Откуда вас забрать? Напишите адрес:",
        "pickup_c": "📌 Откуда забрать груз? Напишите адрес:",
        "phone": "📞 Отправьте номер телефона для связи кнопкой ниже (отправится номер, на который открыт ваш Telegram):",
        "share": "📱 Отправить номер",
        "bad_num": "❗ Введите только число.",
        "own_phone": "❗ Отправьте только свой номер (кнопкой ниже).",
        "use_btn": "❗ Пожалуйста, нажмите кнопку ниже.",
        "use_inline": "👆 Пожалуйста, выберите одну из кнопок.",
        "check": "Проверьте ваши данные:",
        "order": "✅ Заказать",
        "placed": "✅ Заказ №{id} принят.\n⏳ Статус: в процессе. Мы сообщим, как только найдётся водитель.",
        "cancel": "❌ Отменить", "new": "➕ Новый заказ",
        "cancelled": "❌ Заказ №{id} отменён.",
        "cant_cancel": "Этот заказ нельзя отменить: водитель найден. Посмотрите его данные и примите или отклоните.",
        "drv": "🚖 Для заказа №{id} найден водитель!",
        "accept": "✅ Принять", "reject": "❌ Отклонить",
        "accepted": "✅ Отлично! Свяжитесь с водителем по телефону. Счастливого пути! 🚕",
        "rejected": "Водитель отклонён. Заказ №{id} снова в процессе ⏳",
        "error": "⚠️ Произошла ошибка, попробуйте чуть позже.",
        "old": "Эта кнопка устарела.", "cur": "сум",
        "L": {"from": "Откуда", "to": "Куда", "people": "Кол-во человек", "weight": "Вес",
              "price": "Цена", "comment": "Комментарий", "pickup": "Место посадки", "phone": "Телефон"},
        "D": {"name": "Имя фамилия", "birth": "Дата рождения", "phone": "Телефон",
              "num": "Гос. номер", "car": "Марка и цвет"},
    },
}

STEPS = {
    "p": ["from", "to", "people", "price", "comment", "pickup", "phone", "confirm"],
    "c": ["from", "to", "weight", "price", "comment", "pickup", "phone", "confirm"],
}


# ---------------------------------------------------------------- Baza
async def init_db():
    global pool
    pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=1, max_size=5,
        max_inactive_connection_lifetime=30, timeout=30)
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id SERIAL PRIMARY KEY,
            kind TEXT, from_city TEXT, to_city TEXT, people TEXT, comment TEXT,
            price BIGINT, pickup TEXT, phone TEXT, tg_id BIGINT, user_name TEXT,
            status TEXT DEFAULT 'open', created TIMESTAMPTZ DEFAULT NOW())""")
    for col in ("lang TEXT", "men INT DEFAULT 0", "women INT DEFAULT 0", "weight TEXT"):
        await pool.execute(f"ALTER TABLE orders ADD COLUMN IF NOT EXISTS {col}")
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS drivers(
            tg_id BIGINT PRIMARY KEY, full_name TEXT, birth_date TEXT, phone TEXT,
            car_number TEXT, car_model TEXT, car_color TEXT, passport_file_id TEXT,
            routes TEXT, approved BOOLEAN DEFAULT FALSE, balance BIGINT DEFAULT 0,
            created TIMESTAMPTZ DEFAULT NOW())""")
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS purchases(
            id SERIAL PRIMARY KEY, order_id INT, driver_id BIGINT, price BIGINT,
            status TEXT DEFAULT 'active', notified BOOLEAN DEFAULT FALSE,
            created TIMESTAMPTZ DEFAULT NOW())""")


# ---------------------------------------------------------------- Yordamchilar
async def kill(msg: Message):
    try:
        await msg.delete()
    except Exception:
        pass


async def drop_kb(m: Message):
    """Pastdagi (reply) klaviaturani olib tashlaydi."""
    try:
        tmp = await m.answer("…", reply_markup=ReplyKeyboardRemove())
        await tmp.delete()
    except Exception:
        pass


def lang_kb():
    return IM(inline_keyboard=[
        [IB(text="🇺🇿 O'zbekcha (lotin)", callback_data="lang:uz")],
        [IB(text="🇺🇿 Ўзбекча (кирил)", callback_data="lang:oz")],
        [IB(text="🇷🇺 Русский", callback_data="lang:ru")],
    ])


def service_kb(t):
    return IM(inline_keyboard=[
        [IB(text=t["p"], callback_data="svc:p")],
        [IB(text=t["c"], callback_data="svc:c")],
        [IB(text=t["back"], callback_data="back_lang")],
    ])


def region_kb(lang, skip_idx, t):
    btns = [IB(text=reg(lang, i), callback_data=f"r:{i}")
            for i in range(len(REG)) if i != skip_idx]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    rows.append([IB(text=t["back"], callback_data="back")])
    return IM(inline_keyboard=rows)


def people_text(t, d):
    m, w = d.get("men", 0), d.get("women", 0)
    return (t["people"].format(max=MAX_PEOPLE) + "\n\n" +
            t["people_now"].format(m=m, w=w, t=m + w, max=MAX_PEOPLE))


def people_kb(t):
    return IM(inline_keyboard=[
        [IB(text=t["men"], callback_data="pp:m"), IB(text=t["women"], callback_data="pp:w")],
        [IB(text=t["clear"], callback_data="pp:x"), IB(text=t["next"], callback_data="pp:ok")],
        [IB(text=t["back"], callback_data="back")],
    ])


def summary(d):
    lang, a, t = d["lang"], d["a"], T[d["lang"]]
    L = t["L"]
    lines = [f"📍 {L['from']}: {reg(lang, a['from'])}", f"🏁 {L['to']}: {reg(lang, a['to'])}"]
    if d["kind"] == "p":
        lines.append(f"👥 {L['people']}: {a['people']} (👨 {d['men']} · 👩 {d['women']})")
    else:
        lines.append(f"⚖️ {L['weight']}: {a['weight']} kg")
    price = f"{a['price']:,}".replace(",", " ")
    lines += [f"💰 {L['price']}: {price} {t['cur']}",
              f"📝 {L['comment']}: {a['comment']}",
              f"📌 {L['pickup']}: {a['pickup']}",
              f"📞 {L['phone']}: {a['phone']}"]
    return "\n".join(lines)


async def render(msg: Message, st: FSMContext):
    """Joriy bosqichni ekranga chiqaradi."""
    d = await st.get_data()
    lang, kind = d["lang"], d["kind"]
    t = T[lang]
    key = d["steps"][d["i"]]
    back = [IB(text=t["back"], callback_data="back")]

    if key in ("from", "to"):
        skip = d["a"].get("from") if key == "to" else None
        await msg.answer(t[f"{key}_{kind}"], reply_markup=region_kb(lang, skip, t))
    elif key == "people":
        await msg.answer(people_text(t, d), reply_markup=people_kb(t))
    elif key == "weight":
        await msg.answer(t["weight"], reply_markup=IM(inline_keyboard=[back]))
    elif key == "price":
        await msg.answer(t[f"price_{kind}"], reply_markup=IM(inline_keyboard=[back]))
    elif key == "comment":
        rows = [[IB(text=t["skip"], callback_data="skip")]] if kind == "p" else []
        await msg.answer(t[f"comment_{kind}"], reply_markup=IM(inline_keyboard=rows + [back]))
    elif key == "pickup":
        await msg.answer(t[f"pickup_{kind}"], reply_markup=IM(inline_keyboard=[back]))
    elif key == "phone":
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=t["share"], request_contact=True)],
                      [KeyboardButton(text=t["back"])]],
            resize_keyboard=True)
        await msg.answer(t["phone"], reply_markup=kb)
    elif key == "confirm":
        kb = IM(inline_keyboard=[[IB(text=t["order"], callback_data="ok")], back])
        await msg.answer(f"{t['check']}\n\n{summary(d)}", reply_markup=kb)


async def restart(msg: Message, st: FSMContext):
    await st.clear()
    await msg.answer(START_TEXT, reply_markup=lang_kb())


async def get_flow(c: CallbackQuery, st: FSMContext):
    """Jarayon ma'lumotlarini qaytaradi; yo'q bo'lsa boshidan boshlaydi."""
    d = await st.get_data()
    if not d.get("steps"):
        await kill(c.message)
        await restart(c.message, st)
        await c.answer()
        return None
    return d


# ---------------------------------------------------------------- Boshlash
@dp.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(START_TEXT, reply_markup=lang_kb())


@dp.callback_query(F.data.startswith("lang:"))
async def choose_lang(c: CallbackQuery, state: FSMContext):
    lang = c.data.split(":")[1]
    await state.clear()
    await state.update_data(lang=lang)
    await kill(c.message)
    await c.message.answer(T[lang]["service"], reply_markup=service_kb(T[lang]))
    await c.answer()


@dp.callback_query(F.data == "back_lang")
async def back_lang(c: CallbackQuery, state: FSMContext):
    await kill(c.message)
    await restart(c.message, state)
    await c.answer()


@dp.callback_query(F.data == "new")
async def new_order(c: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if d.get("lang"):
        t = T[d["lang"]]
        await state.set_state(None)
        await c.message.answer(t["service"], reply_markup=service_kb(t))
    else:
        await restart(c.message, state)
    await c.answer()


@dp.callback_query(F.data.startswith("svc:"))
async def choose_service(c: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if not d.get("lang"):
        await kill(c.message)
        await restart(c.message, state)
        return await c.answer()
    kind = c.data.split(":")[1]
    await state.update_data(kind=kind, steps=STEPS[kind], i=0, a={}, men=0, women=0)
    await state.set_state(Flow.s)
    await kill(c.message)
    await render(c.message, state)
    await c.answer()


# ---------------------------------------------------------------- Ortga
@dp.callback_query(F.data == "back")
async def go_back(c: CallbackQuery, state: FSMContext):
    d = await get_flow(c, state)
    if not d:
        return
    await kill(c.message)
    if d["i"] == 0:
        await state.set_state(None)
        t = T[d["lang"]]
        await c.message.answer(t["service"], reply_markup=service_kb(t))
    else:
        await state.update_data(i=d["i"] - 1)
        await render(c.message, state)
    await c.answer()


# ---------------------------------------------------------------- Tugmali bosqichlar
@dp.callback_query(F.data.startswith("r:"))
async def pick_region(c: CallbackQuery, state: FSMContext):
    d = await get_flow(c, state)
    if not d:
        return
    key = d["steps"][d["i"]]
    if key not in ("from", "to"):
        return await c.answer()
    a = d["a"]
    a[key] = int(c.data.split(":")[1])
    await state.update_data(a=a, i=d["i"] + 1)
    await kill(c.message)
    await render(c.message, state)
    await c.answer()


@dp.callback_query(F.data.startswith("pp:"))
async def pick_people(c: CallbackQuery, state: FSMContext):
    d = await get_flow(c, state)
    if not d:
        return
    if d["steps"][d["i"]] != "people":
        return await c.answer()
    t = T[d["lang"]]
    act = c.data.split(":")[1]
    m, w = d["men"], d["women"]

    if act in ("m", "w"):
        if m + w >= MAX_PEOPLE:
            return await c.answer(t["max"].format(max=MAX_PEOPLE), show_alert=True)
        m, w = (m + 1, w) if act == "m" else (m, w + 1)
    elif act == "x":
        m = w = 0
    elif act == "ok":
        if m + w == 0:
            return await c.answer(t["need_one"], show_alert=True)
        a = d["a"]
        a["people"] = m + w
        await state.update_data(a=a, i=d["i"] + 1)
        await kill(c.message)
        await render(c.message, state)
        return await c.answer()

    await state.update_data(men=m, women=w)
    d = await state.get_data()
    try:
        await c.message.edit_text(people_text(t, d), reply_markup=people_kb(t))
    except TelegramBadRequest:
        pass
    await c.answer()


@dp.callback_query(F.data == "skip")
async def skip_comment(c: CallbackQuery, state: FSMContext):
    d = await get_flow(c, state)
    if not d:
        return
    if d["steps"][d["i"]] != "comment":
        return await c.answer()
    a = d["a"]
    a["comment"] = "-"
    await state.update_data(a=a, i=d["i"] + 1)
    await kill(c.message)
    await render(c.message, state)
    await c.answer()


# ---------------------------------------------------------------- Matnli bosqichlar
@dp.message(Flow.s, F.text | F.contact)
async def text_step(m: Message, state: FSMContext):
    d = await state.get_data()
    if not d.get("steps"):
        return await restart(m, state)
    t = T[d["lang"]]
    key = d["steps"][d["i"]]
    a = d["a"]

    # pastdagi "Ortga" (reply) tugmasi, faqat telefon bosqichida
    if key == "phone" and m.text == t["back"]:
        await drop_kb(m)
        await state.update_data(i=d["i"] - 1)
        return await render(m, state)

    if key == "weight":
        try:
            v = float((m.text or "").replace(",", ".").strip())
            assert 0 < v <= 50000
        except Exception:
            return await m.answer(t["bad_num"])
        a["weight"] = str(int(v)) if v == int(v) else str(v)

    elif key == "price":
        raw = (m.text or "").replace(" ", "").replace(",", "").replace(".", "")
        if not raw.isdigit() or int(raw) <= 0:
            return await m.answer(t["bad_num"])
        a["price"] = int(raw)

    elif key in ("comment", "pickup"):
        if not m.text:
            return
        a[key] = m.text.strip()[:500]

    elif key == "phone":
        if not m.contact:
            return await m.answer(t["use_btn"])
        if m.contact.user_id != m.from_user.id:
            return await m.answer(t["own_phone"])
        ph = m.contact.phone_number
        a["phone"] = ph if ph.startswith("+") else "+" + ph
        await drop_kb(m)

    else:  # tugma kutilayotgan bosqich
        return await m.answer(t["use_inline"])

    await state.update_data(a=a, i=d["i"] + 1)
    await render(m, state)


# ---------------------------------------------------------------- Buyurtma berish / bekor qilish
def placed_kb(t, oid):
    return IM(inline_keyboard=[
        [IB(text=t["cancel"], callback_data=f"cancel:{oid}")],
        [IB(text=t["new"], callback_data="new")],
    ])


@dp.callback_query(F.data == "ok")
async def place_order(c: CallbackQuery, state: FSMContext):
    uid = c.from_user.id
    d = await state.get_data()
    if uid in busy or not d.get("steps") or d["steps"][d["i"]] != "confirm":
        return await c.answer()
    busy.add(uid)
    lang = d["lang"]
    t = T[lang]
    try:
        a = d["a"]
        oid = await pool.fetchval(
            """INSERT INTO orders(kind, from_city, to_city, people, men, women, weight,
                                  comment, price, pickup, phone, tg_id, user_name, lang)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14) RETURNING id""",
            d["kind"], REG[a["from"]][0], REG[a["to"]][0],
            str(a["people"]) if d["kind"] == "p" else None,
            d["men"], d["women"], a.get("weight"),
            a["comment"], a["price"], a["pickup"], a["phone"],
            uid, c.from_user.full_name, lang)
        await state.clear()
        await state.update_data(lang=lang)
        await kill(c.message)
        await c.message.answer(t["placed"].format(id=oid), reply_markup=placed_kb(t, oid))
    except Exception:
        logging.exception("order insert failed")
        await c.message.answer(t["error"])
    finally:
        busy.discard(uid)
    await c.answer()


@dp.callback_query(F.data.startswith("cancel:"))
async def cancel_order(c: CallbackQuery, state: FSMContext):
    oid = int(c.data.split(":")[1])
    d = await state.get_data()
    t = T[d.get("lang", "uz")]
    row = await pool.fetchrow(
        "UPDATE orders SET status='cancelled' WHERE id=$1 AND tg_id=$2 AND status='open' RETURNING id",
        oid, c.from_user.id)
    if row:
        await c.message.edit_text(
            t["cancelled"].format(id=oid),
            reply_markup=IM(inline_keyboard=[[IB(text=t["new"], callback_data="new")]]))
    else:
        await c.message.answer(t["cant_cancel"])
    await c.answer()


# ---------------------------------------------------------------- Haydovchi topilganda
async def notify_purchase(pid: int):
    """Haydovchi buyurtmani sotib olganda chaqiriladi (haydovchi mini-appi shu jarayonda
    ishlasa, to'g'ridan-to'g'ri chaqirish mumkin): yo'lovchiga haydovchi ma'lumotini yuboradi."""
    r = await pool.fetchrow(
        """SELECT p.order_id, o.tg_id AS passenger, o.lang, d.full_name, d.birth_date,
                  d.phone, d.car_number, d.car_model, d.car_color
           FROM purchases p JOIN orders o ON o.id=p.order_id
           JOIN drivers d ON d.tg_id=p.driver_id
           WHERE p.id=$1 AND p.status='active' AND NOT p.notified""", pid)
    if not r:
        return
    await pool.execute("UPDATE purchases SET notified=TRUE WHERE id=$1", pid)
    lang = r["lang"] or "uz"
    t, D = T[lang], T[lang]["D"]
    text = (f"{t['drv'].format(id=r['order_id'])}\n\n"
            f"👤 {D['name']}: {r['full_name']}\n"
            f"🎂 {D['birth']}: {r['birth_date']}\n"
            f"📞 {D['phone']}: {r['phone']}\n"
            f"🔢 {D['num']}: {r['car_number']}\n"
            f"🚘 {D['car']}: {r['car_model']}, {r['car_color']}")
    kb = IM(inline_keyboard=[[IB(text=t["accept"], callback_data=f"acc:{pid}"),
                              IB(text=t["reject"], callback_data=f"rej:{pid}")]])
    try:
        await bot.send_message(r["passenger"], text, reply_markup=kb)
    except Exception:
        logging.exception("notify failed")


@dp.callback_query(F.data.startswith("acc:"))
async def accept_driver(c: CallbackQuery, state: FSMContext):
    pid = int(c.data.split(":")[1])
    d = await state.get_data()
    lang = d.get("lang", "uz")
    row = await pool.fetchrow(
        """UPDATE purchases p SET status='accepted' FROM orders o
           WHERE p.id=$1 AND p.status='active' AND o.id=p.order_id AND o.tg_id=$2
           RETURNING p.order_id""", pid, c.from_user.id)
    if not row:
        return await c.answer(T[lang]["old"], show_alert=True)
    await pool.execute("UPDATE orders SET status='accepted' WHERE id=$1", row["order_id"])
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.answer(T[lang]["accepted"])
    await c.answer()


@dp.callback_query(F.data.startswith("rej:"))
async def reject_driver(c: CallbackQuery, state: FSMContext):
    pid = int(c.data.split(":")[1])
    d = await state.get_data()
    lang = d.get("lang", "uz")
    t = T[lang]
    async with pool.acquire() as con:
        async with con.transaction():
            row = await con.fetchrow(
                """UPDATE purchases p SET status='rejected' FROM orders o
                   WHERE p.id=$1 AND p.status='active' AND o.id=p.order_id AND o.tg_id=$2
                   RETURNING p.order_id, p.driver_id, p.price""", pid, c.from_user.id)
            if row:
                await con.execute("UPDATE orders SET status='open' WHERE id=$1", row["order_id"])
                await con.execute(
                    "UPDATE drivers SET balance = balance + $2 WHERE tg_id=$1",
                    row["driver_id"], row["price"] * REFUND_PERCENT // 100)
    if not row:
        return await c.answer(t["old"], show_alert=True)
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.answer(t["rejected"].format(id=row["order_id"]),
                           reply_markup=placed_kb(t, row["order_id"]))
    await c.answer()


# ---------------------------------------------------------------- Boshqa xabarlar
@dp.message(StateFilter(None))
async def fallback(m: Message, state: FSMContext):
    await restart(m, state)


# ---------------------------------------------------------------- Uxlab qolmaslik uchun
async def health(_):
    return web.Response(text="ok")


async def run_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()


async def keepalive():
    """Render bepul xizmati 15 daqiqa so'rovsiz qolsa uxlaydi. O'zimizga har 10 daqiqada
    so'rov yuborib uni uyg'oq ushlaymiz."""
    if not SELF_URL:
        return
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        while True:
            await asyncio.sleep(600)
            try:
                await s.get(SELF_URL)
            except Exception:
                logging.warning("keepalive failed")


async def main():
    await init_db()
    await run_web()
    asyncio.create_task(keepalive())
    # bot o'chib turgan paytda sotib olingan, lekin xabar yuborilmagan buyurtmalar
    for r in await pool.fetch("SELECT id FROM purchases WHERE status='active' AND NOT notified"):
        await notify_purchase(r["id"])
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
