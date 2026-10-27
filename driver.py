"""Safar Driver: haydovchi boti + Mini App serveri (main.py bilan bir jarayonda ishlaydi).

Render -> Environment:  DRIVER_BOT_TOKEN, ADMIN_ID
"""
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton as IB,
    InlineKeyboardMarkup as IM, KeyboardButton, Message, ReplyKeyboardMarkup,
    ReplyKeyboardRemove, WebAppInfo,
)
from aiohttp import web

TOKEN = os.environ.get("DRIVER_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0") or 0)
BASE_URL = (os.environ.get("WEBAPP_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")

enabled = bool(TOKEN)
bot = Bot(TOKEN) if enabled else None
dp = Dispatcher()
pool = None


async def setup(p):
    global pool
    pool = p
    if not enabled:
        logging.warning("DRIVER_BOT_TOKEN yo'q: haydovchi boti o'chirilgan")