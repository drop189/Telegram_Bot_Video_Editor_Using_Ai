import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from config import dp, SUBSCRIBED_USERS
from services.ai_service import AI_STANDARD_THEME
from states import VideoProcessing
from utils.subscribers import save_subscribed_users

router = Router()

# ============ КОМАНДЫ БОТА ============

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Добавляем пользователя в подписчики
    if user_id not in SUBSCRIBED_USERS:
        SUBSCRIBED_USERS.add(user_id)
        save_subscribed_users()
        logging.info(f"Новый пользователь подписался: {user_id} ({username})")

    await message.answer(
        "👋 Привет! Я бот для обработки видео с философскими текстами о барберинге.\n\n"
        "📌 Как это работает:\n"
        "1. Выбери тему для текста (или используй стандартную)\n"
        "2. Отправь видео\n"
        "3. Я добавлю текст на видео и сгенерирую описание\n\n"
        "✏️ Чтобы начать, отправь свою тему для текста (например: 'стиль, уход, профессия')\n"
        "📝 Или просто отправь видео - тогда будет использована стандартная тема\n\n"
        "ℹ️ Теперь вы будете получать уведомления о статусе бота!"
    )
    await state.set_state(VideoProcessing.waiting_for_theme)


# Команда /default - использовать стандартную тему
@dp.message(Command("default"))
async def cmd_default(message: Message, state: FSMContext):
    await state.update_data(theme=AI_STANDARD_THEME)
    await message.answer(
        f"✅ Использую стандартную тему: '{AI_STANDARD_THEME}'\n\n"
        "Теперь отправь мне видео для обработки! 🎬"
    )
    await state.set_state(VideoProcessing.waiting_for_video)


# Команда /cancel - отмена
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Операция отменена. Используйте /start чтобы начать заново.")
