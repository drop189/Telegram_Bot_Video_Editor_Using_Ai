import asyncio
import logging
import os

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile

from bot.dispatcher import bot
from bot.states import VideoProcessing
from services.ai_service import AI_STANDARD_THEME
from services.stats_service import usage_stats
from services.video_editor import process_single_video
from settings.config import VIDEOS_FOLDER, OUTPUT_FOLDER
from settings.logging import self_logger

router = Router()


# ============ ХЕНДЛЕРЫ БОТА ============

# Обработка видео с сохраненной темой
@router.message(VideoProcessing.waiting_for_video, F.video)
@self_logger
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
@router.message(F.video)
@self_logger
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
@router.message(VideoProcessing.waiting_for_theme, F.photo)
@self_logger
async def handle_photo_in_theme_state(message: Message):
    await message.answer(
        "📌 Вы отправили фото, но я ожидаю тему для текста.\n\n"
        "Пожалуйста, отправьте текстовое сообщение с темой (например: 'стиль, уход, профессия')\n"
        "Или используйте /default для стандартной темы"
    )


# Если в состоянии waiting_for_theme пришел документ
@router.message(VideoProcessing.waiting_for_theme, F.document)
@self_logger
async def handle_document_in_theme_state(message: Message):
    await message.answer(
        "📌 Вы отправили документ, но я ожидаю тему для текста.\n\n"
        "Пожалуйста, отправьте текстовое сообщение с темой (например: 'стиль, уход, профессия')\n"
        "Или используйте /default для стандартной темы"
    )


# Обработка текстовых сообщений в неправильном состоянии
@router.message(VideoProcessing.processing)
@self_logger
async def handle_text_while_processing(message: Message):
    await message.answer("⏳ Пожалуйста, подождите, текущее видео еще обрабатывается...")


# Получение темы от пользователя - ТОЛЬКО для текстовых сообщений
@router.message(VideoProcessing.waiting_for_theme, F.text)
@self_logger
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


# Обработка обычных текстовых сообщений (без состояния или в других состояниях)
@router.message(F.text)
@self_logger
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
        await state.set_state(VideoProcessing.waiting_for_theme)
    elif current_state == VideoProcessing.processing:
        # Уже обрабатывается в отдельном хендлере, но на всякий случай
        await message.answer("⏳ Пожалуйста, подождите, текущее видео еще обрабатывается...")
    else:
        # В других случаях (например, в waiting_for_theme), на будущее, если будеи расширяться
        # Этот случай уже обрабатывается хендлером process_theme (waiting_for_theme)
        pass


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
        start_time = asyncio.get_event_loop().time()

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

        # Отправляем описание отдельным сообщением
        if desc and desc != "Описание не сгенерировано":
            # Форматируем описание для лучшей читаемости
            description_text = f"""
📝 ОПИСАНИЕ ДЛЯ INSTAGRAM:
```Копировать
{desc}
```
✨ Текст на видео: "{title}"
🎯 Тема: {used_theme}
                """

            # Разбиваем на части если слишком длинное (ограничение Telegram)
            if len(description_text) > 4096:
                parts = [description_text[i:i + 4000] for i in range(0, len(description_text), 4000)]
                for part in parts:
                    await message.answer(part)
            else:
                await message.answer(description_text, parse_mode='Markdown')

        await status_message.delete()

        await message.answer(
            "✅ Готово! Видео обработано успешно.\n\n"
            "Хочешь обработать еще одно видео?\n"
            "1. Отправь новую тему для текста\n"
            "2. Или просто отправь следующее видео - будет использована стандартная тема\n\n"
            "Для отмены используй /cancel"
        )

        processing_time = asyncio.get_event_loop().time() - start_time

        usage_stats.record_video_processed(
            user_id=message.from_user.id,
            processing_time=processing_time,
            theme=theme,
            content_length=len(desc) if desc else 0
        )
        await state.set_state(VideoProcessing.waiting_for_theme)

    except Exception as e:
        logging.exception("Ошибка обработки видео")
        error_type = type(e).__name__
        error_msg = str(e)
        usage_stats.record_error(
            user_id=message.from_user.id,
            error_type=error_type,
            error_message=error_msg[:200]
        )
        await message.answer(f"❌ Ошибка: {e}")
        await state.clear()

    finally:
        for path in (input_path, output_path):
            if path and os.path.exists(path):
                os.remove(path)
