import asyncio
import logging
import os
import sqlite3
import io
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, PreCheckoutQuery
import google.generativeai as genai
from google.genai import types as genai_types

logging.basicConfig(level=logging.INFO)

# ================= НАСТРОЙКИ И КЛЮЧИ =================
# Вставь свой актуальный токен от @BotFather в кавычки:
BOT_TOKEN = "9186913801:AAESm9mt5iaKboWZAtiy8W7O5O0SMD9dW2o"
# Вставь свой ключ от Google AI Studio (Gemini):
GEMINI_API_KEY = "AQ.Ab8RN6LkwHctTXnLNkVyk6Oia_3Ji_XaB4xdzZbxvhukdH-HNQ"
# Токен из @CryptoBot (раздел Crypto Pay -> Создать приложение), если принимаешь USDT:
CRYPTO_PAY_TOKEN = ""

FREE_LIMIT = 15
PRO_STARS_PRICE = 150  # ~ $2.5 - $3
PRO_USDT_PRICE = "2.5"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
genai.configure(api_key=GEMINI_API_KEY)

# ================= БАЗА ДАННЫХ =================
conn = sqlite3.connect("hvosty_pro.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    mode TEXT DEFAULT 'reshala',
    requests_count INTEGER DEFAULT 0,
    is_pro INTEGER DEFAULT 0
)
""")
conn.commit()

def get_user(user_id: int):
    cursor.execute("SELECT mode, requests_count, is_pro FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return ("reshala", 0, 0)
    return row

def update_mode(user_id: int, mode: str):
    get_user(user_id)
    cursor.execute("UPDATE users SET mode = ? WHERE user_id = ?", (mode, user_id))
    conn.commit()

def increment_requests(user_id: int):
    cursor.execute("UPDATE users SET requests_count = requests_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def set_pro(user_id: int):
    cursor.execute("UPDATE users SET is_pro = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

# ================= КЛАВИАТУРЫ =================
def get_mode_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕶 Решала (Жёстко и по делу)", callback_data="set_mode_reshala"),
        ],
        [
            InlineKeyboardButton(text="🎩 Дворецкий (Вежливо и структурно)", callback_data="set_mode_butler")
        ]
    ])

def get_pay_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐️ Оплатить {PRO_STARS_PRICE} Stars (PRO)", callback_data="buy_stars")],
        [InlineKeyboardButton(text=f"💎 Оплатить {PRO_USDT_PRICE} USDT (CryptoBot)", callback_data="buy_crypto")]
    ])

# ================= СИСТЕМНЫЕ ПРОМПТЫ =================
def get_system_instruction(mode: str) -> str:
    base_rules = (
        "Твоя главная задача — проанализировать входящее сообщение пользователя (текст, скриншот переписки или голосовое сообщение) "
        "и разложить информацию строго по 4 категориям:\n"
        "1. 📌 Мои хвосты (My loose ends) — что нужно сделать самому.\n"
        "2. ⏳ Должники и динамисты (Debtors/Flakes) — кто должен деньги, ответ или обещал что-то сделать.\n"
        "3. 💰 Деньги (Money) — суммы, оплаты, бюджеты, счета.\n"
        "4. 💡 Идеи (Ideas) — инсайты, задумки, гипотезы.\n\n"
        "Если какая-то категория пуста, не пиши её. Выдели конкретные шаги, имена и сроки. Отвечай на языке пользователя (RU или EN)."
    )
    if mode == "butler":
        return (
            "Ты — элитный, безупречно вежливый и педантичный личный Дворецкий. "
            "Обращайся к пользователю с уважением (например, «Сэр» или «Босс»), подавай информацию максимально аккуратно, структурно и дипломатично.\n"
            + base_rules
        )
    else:
        return (
            "Ты — РЕШАЛА, жёсткий теневой менеджер и раскидыватель хвостов. "
            "Общайся дерзко, конкретно, без воды и соплей, как опытный напарник, который наводит порядок в делах.\n"
            + base_rules
        )

# ================= ОБРАБОТКА КОМАНД =================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_user(message.from_user.id)
    text = (
        "👋 **Привет! На связи твой ИИ-ассистент.**\n\n"
        "Кидай мне **текст, голосовые сообщения или скриншоты переписок** — я вытащу суть и раскидаю всё по 4 полочкам: "
        "*Хвосты, Должники, Деньги и Идеи*.\n\n"
        "👇 **Для начала выбери стиль работы:**"
    )
    await message.answer(text, reply_markup=get_mode_keyboard(), parse_mode="Markdown")

@dp.message(Command("mode"))
async def cmd_mode(message: types.Message):
    await message.answer("Выбери режим общения:", reply_markup=get_mode_keyboard())

@dp.message(Command("pro"))
async def cmd_pro(message: types.Message):
    await message.answer(
        "🚀 **PRO-доступ без ограничений**\n\n"
        "Снимает лимит в 15 запросов, открывает безлимитный разбор голосовых и скриншотов 24/7.",
        reply_markup=get_pay_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("set_mode_"))
async def callback_set_mode(callback: types.CallbackQuery):
    mode = callback.data.replace("set_mode_", "")
    update_mode(callback.from_user.id, mode)
    if mode == "butler":
        msg = "🎩 Режим **«Дворецкий»** активирован. К вашим услугам, сэр! Жду ваших поручений, голосовых или скриншотов."
    else:
        msg = "🕶 Режим **«Решала»** в деле. Без соплей и лишних кнопок — закидывай голосовуху, текст или скрин, раскидаем."
    await callback.message.edit_text(msg, parse_mode="Markdown")
    await callback.answer()

# ================= ОПЛАТА (STARS & CRYPTOBOT) =================
@dp.callback_query(F.data == "buy_stars")
async def process_buy_stars(callback: types.CallbackQuery):
    prices = [LabeledPrice(label="PRO Access (Unlimited)", amount=PRO_STARS_PRICE)]
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="PRO-доступ | ИИ-Напарник",
        description="Безлимитный разбор задач, голосовых и скриншотов",
        payload="pro_subscription",
        provider_token="",  # Для Telegram Stars токен оставляется пустым
        currency="XTR",
        prices=prices
    )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    set_pro(message.from_user.id)
    await message.answer("🔥 Оплата прошла! Твой аккаунт переведен в **PRO-статус**. Лимиты сняты!", parse_mode="Markdown")

@dp.callback_query(F.data == "buy_crypto")
async def process_buy_crypto(callback: types.CallbackQuery):
    if not CRYPTO_PAY_TOKEN:
        await callback.message.answer(
            "💎 Оплата в USDT временно настраивается. Для моментальной активации воспользуйся оплатой через **Telegram Stars** выше.",
            parse_mode="Markdown"
        )
    else:
        await callback.message.answer(f"💎 Для оплаты {PRO_USDT_PRICE} USDT перейди в @CryptoBot и оплати выставленный счет.")
    await callback.answer()

# ================= ИИ-ОБРАБОТКА (ТЕКСТ, ФОТО, ГОЛОС) =================
async def check_limits(message: types.Message) -> bool:
    mode, count, is_pro = get_user(message.from_user.id)
    if is_pro == 0 and count >= FREE_LIMIT:
        await message.answer(
            f"⛔️ Бесплатный лимит ({FREE_LIMIT} запросов) исчерпан.\n\nОформи PRO-доступ, чтобы продолжить работу без ограничений:",
            reply_markup=get_pay_keyboard()
        )
        return False
    return True

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    if not await check_limits(message):
        return
    mode, _, _ = get_user(message.from_user.id)
    wait_msg = await message.answer("📸 Принял скриншот. Сканирую детали...")
    try:
        photo = message.photo[-1]
        file_io = io.BytesIO()
        await bot.download(photo, destination=file_io)
        image_bytes = file_io.getvalue()

        response = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=get_system_instruction(mode)
).generate_content(
    [
        genai.types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        caption
    ]
        )
        
        increment_requests(message.from_user.id)
        await wait_msg.edit_text(response.text)
    except Exception as e:
        logging.error(f"Photo error: {e}")
        await wait_msg.edit_text("⚠️ Не удалось разобрать изображение. Попробуй прислать еще раз.")

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    if not await check_limits(message):
        return
    mode, _, _ = get_user(message.from_user.id)
    wait_msg = await message.answer("🎙 Слушаю голосовое и раскладываю по полкам...")
    try:
        voice = message.voice
        file_io = io.BytesIO()
        await bot.download(voice, destination=file_io)
        audio_bytes = file_io.getvalue()

        response = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=get_system_instruction(mode)
        ).generate_content(
            [
                genai.types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
               "Расшифруй это голосовое сообщение и разложи суть по 4 категориям: Мои хвосты, Должники/динамисты, Деньги, Идеи."
            ]
        )
        increment_requests(message.from_user.id)
        await wait_msg.edit_text(response.text)
    except Exception as e:
        logging.error(f"Voice error: {e}")
        await wait_msg.edit_text("⚠️ Ошибка при распознавании голоса. Попробуй записать еще раз.")

@dp.message(F.text)
async def handle_text(message: types.Message):
    if not await check_limits(message):
        return
    mode, _, _ = get_user(message.from_user.id)
    wait_msg = await message.answer("⚡️ Раскидываю задачу...")
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=message.text,
            config=genai_types.GenerateContentConfig(
                system_instruction=get_system_instruction(mode)
            )
        )
        increment_requests(message.from_user.id)
        await wait_msg.edit_text(response.text)
    except Exception as e:
        logging.error(f"Text error: {e}")
        await wait_msg.edit_text("⚠️ Сбой связи с нейросетью. Попробуй через пару секунд.")

# ================= ФОНОВЫЙ СЕРВЕР ДЛЯ RENDER =================
async def health_check(request):
    return web.Response(text="Reshala Bot is Alive!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_dummy_server()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
