import asyncio
import logging
import os
import textwrap

from aiogram import F
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile
from config import bot, VIDEOS_FOLDER, OUTPUT_FOLDER, dp
from services.ai_service import AI_STANDARD_THEME
from services.video_editor import process_single_video
from states import VideoProcessing


# ============ ХЕНДЛЕРЫ БОТА ============

# Обработка видео с сохраненной темой
@dp.message(VideoProcessing.waiting_for_video, F.video)
async def handle_video_with_theme(message: Message, state: FSMContext):
    data = await state.get_data()
    theme = data.get("theme", AI_STANDARD_THEME)

    await process_video(
        message,
        state,
        theme,
        f"🎬 Видео получено.\n"
        f"📌 Тема: '{theme}'\n"
        f"⏳ Начинаю обработку..."
    )


# Обработка видео БЕЗ предварительного выбора темы (используется стандартная тема)
@dp.message(F.video)
async def handle_video_without_theme(message: Message, state: FSMContext):
    if await state.get_state() == VideoProcessing.waiting_for_video:
        return

    await process_video(
        message,
        state,
        AI_STANDARD_THEME,
        f"🎬 Видео получено.\n"
        f"📌 Использую стандартную тему: '{AI_STANDARD_THEME}'\n"
        f"⏳ Начинаю обработку..."
    )


# Если в состоянии waiting_for_theme пришло фото
@dp.message(VideoProcessing.waiting_for_theme, F.photo)
async def handle_photo_in_theme_state(message: Message):
    await message.answer(
        "📌 Вы отправили фото, но я ожидаю тему для текста.\n\n"
        "Пожалуйста, отправьте текстовое сообщение с темой (например: 'стиль, уход, профессия')\n"
        "Или используйте /default для стандартной темы"
    )


# Если в состоянии waiting_for_theme пришел документ
@dp.message(VideoProcessing.waiting_for_theme, F.document)
async def handle_document_in_theme_state(message: Message):
    await message.answer(
        "📌 Вы отправили документ, но я ожидаю тему для текста.\n\n"
        "Пожалуйста, отправьте текстовое сообщение с темой (например: 'стиль, уход, профессия')\n"
        "Или используйте /default для стандартной темы"
    )


# Обработка текстовых сообщений в неправильном состоянии
@dp.message(VideoProcessing.processing)
async def handle_text_while_processing(message: Message):
    await message.answer("⏳ Пожалуйста, подождите, текущее видео еще обрабатывается...")


# Обработка обычных текстовых сообщений (без состояния или в других состояниях)
@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    current_state = await state.get_state()

    if current_state is None:
        # Если нет активного состояния, предлагаем начать
        await message.answer("Начните с команды /start")
        await state.set_state(VideoProcessing.waiting_for_theme)
    elif current_state == VideoProcessing.waiting_for_video:
        # Если ожидаем видео, но получили текст
        await message.answer(
            "📌 Я ожидаю видео для обработки.\n\n"
            "Пожалуйста, отправьте видео файлом.\n"
            "Если хотите изменить тему, отправьте команду /start\n"
            "Или используйте /default для стандартной темы"
        )
    elif current_state == VideoProcessing.processing:
        # Уже обрабатывается в отдельном хендлере, но на всякий случай
        await message.answer("⏳ Пожалуйста, подождите, текущее видео еще обрабатывается...")
    else:
        # В других случаях (например, в waiting_for_theme), на будущее, если будеи расширяться
        # Этот случай уже обрабатывается хендлером process_theme (waiting_for_theme)
        pass


# Получение темы от пользователя - ТОЛЬКО для текстовых сообщений
@dp.message(VideoProcessing.waiting_for_theme, F.text)
async def process_theme(message: Message, state: FSMContext):
    # Проверяем, что есть текст
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текстовое сообщение с темой.")
        return

    theme = message.text.strip()

    if len(theme) < 2:
        await message.answer("❌ Тема слишком короткая. Пожалуйста, введите тему подробнее.")
        return

    if len(theme) > 500:
        await message.answer("❌ Тема слишком длинная. Пожалуйста, уложитесь в 500 символов.")
        return

    await state.update_data(theme=theme)

    await message.answer(
        f"✅ Отлично! Тема сохранена: '{theme}'\n\n"
        f"Теперь отправь мне видео для обработки! 🎬\n\n"
        f"📌 Можно отправить видео файлом или как видеосообщение\n"
        f"⏳ Обработка займет несколько минут"
    )

    await state.set_state(VideoProcessing.waiting_for_video)

# Обработка полученного видео общая функция
async def process_video(
        message: Message,
        state: FSMContext,
        theme: str,
        intro_text: str
):
    input_path = None
    output_path = None

    status_message = await message.answer(intro_text)
    await state.set_state(VideoProcessing.processing)

    try:
        os.makedirs(VIDEOS_FOLDER, exist_ok=True)
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        video = message.video
        file_info = await bot.get_file(video.file_id)

        user_id = message.from_user.id
        timestamp = int(asyncio.get_event_loop().time())

        input_path = os.path.join(
            VIDEOS_FOLDER, f"temp_{user_id}_{timestamp}.mp4"
        )
        output_path = os.path.join(
            OUTPUT_FOLDER, f"processed_{user_id}_{timestamp}.mp4"
        )

        await status_message.edit_text("📥 Скачиваю видео...")
        await bot.download_file(file_info.file_path, input_path)

        if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
            raise Exception("Файл не скачался или пустой")

        await status_message.edit_text(
            f"⚙️ Обрабатываю видео...\n"
            f"🤔 Генерирую текст на тему: '{theme}'"
        )

        success, result_msg, title, desc, used_theme = await asyncio.to_thread(
            process_single_video,
            input_path,
            output_path,
            theme
        )

        if not success:
            await status_message.edit_text(f"❌ {result_msg}")
            return

        if not os.path.exists(output_path):
            raise Exception("Обработанное видео не создано")

        await status_message.edit_text("📤 Отправляю результат...")

        if title and len(title) > 1024:
            caption = f"🎬 {title[:1021]}...\n\n📌 Тема: {used_theme}"
        else:
            caption = f"🎬 {title}\n\n📌 Тема: {used_theme}"

        await message.answer_video(
            FSInputFile(output_path),
            caption=caption
        )

        if desc and desc != "Описание не сгенерировано":
            description_text = (
                "📝 ОПИСАНИЕ ДЛЯ INSTAGRAM:\n"
                "-------------------------\n"
                f"{desc}\n\n"
                f"✨ Текст на видео: \"{title}\"\n"
                f"🎯 Тема: {used_theme}"
            )

            for part in textwrap.wrap(description_text, 4000):
                await message.answer(part)

        await status_message.delete()

        await message.answer(
            "✅ Готово! Видео обработано.\n\n"
            "Отправь новую тему или следующее видео.\n"
            "Для отмены — /cancel"
        )

        await state.set_state(VideoProcessing.waiting_for_theme)

    except Exception as e:
        logging.exception("Ошибка обработки видео")
        await message.answer(f"❌ Ошибка: {e}")
        await state.clear()

    finally:
        for path in (input_path, output_path):
            if path and os.path.exists(path):
                os.remove(path)
