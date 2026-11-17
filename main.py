import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google import genai
from google.genai import types as genai_types

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = 9186913801:AAESm9mt5iaKboWZAtiy8W7O5O0SMD9dW2o
GEMINI_API_KEY = "AQ.Ab8RN6LkwHctTXnLNkVyk60ia_3Ji_XaB4xdzZbvhukdH-HNQ"
CRYPTO_PAY_TOKEN = ""

FREE_LIMIT = 15
PRO_STARS_PRICE = 150  # ~ $2.5 - $3
PRO_USDT_PRICE = "2.5"  # $2.5 в USDT

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = genai.Client(api_key=GEMINI_API_KEY)
scheduler = AsyncIOScheduler()

# --- БАЗА ДАННЫХ (SQLite) ---
conn = sqlite3.connect("hvosty_pro.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    lang TEXT DEFAULT 'ru',
    persona TEXT DEFAULT 'reshala',
    requests_left INTEGER DEFAULT 15,
    is_pro INTEGER DEFAULT 0
)
""")
conn.commit()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Погнали / Let's go", callback_data="start_app")]
    ])
    await message.answer(
        "Здорово, начальник. Я **РЕШАЛА** — твой теневой менеджер и раскидыватель хвостов.\n"
        "Кидай мне голосовухи, скриншоты или пересылки чатов — я разложу всё по полочкам.\n\n"
        "Hey boss. I'm **FIXER** — your shadow manager.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "start_app")
async def process_start_app(callback: types.CallbackQuery):
    await callback.message.answer("Бот полностью готов к работе! Отправь мне любую задачу, голосовое или скриншот.")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
