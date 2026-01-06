import asyncio
import logging
import os
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
    # Получаем сохраненную тему
    user_data = await state.get_data()
    theme = user_data.get('theme', AI_STANDARD_THEME)

    # Уведомляем пользователя
    status_message = await message.answer(f"🎬 Видео получено. Тема: '{theme}'\nНачинаю обработку...")

    await state.set_state(VideoProcessing.processing)


    input_path = None
    output_path = None

    try:
        # Создаем рабочие папки
        os.makedirs(VIDEOS_FOLDER, exist_ok=True)
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        # Получаем информацию о файле
        video = message.video
        file_info = await bot.get_file(video.file_id)

        # Генерируем уникальные имена файлов
        user_id = message.from_user.id
        timestamp = int(asyncio.get_event_loop().time())
        input_filename = f"temp_{user_id}_{timestamp}.mp4"
        output_filename = f"processed_{user_id}_{timestamp}.mp4"

        input_path = os.path.join(VIDEOS_FOLDER, input_filename)
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        logging.info(f"Скачиваю видео в: {input_path}")
        logging.info(f"Тема: {theme}")

        # Скачиваем видео
        await status_message.edit_text("📥 Скачиваю видео...")
        try:
            await bot.download_file(file_info.file_path, input_path)
            if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                raise Exception("Файл не скачался или пустой")
            logging.info(f"Файл скачан. Размер: {os.path.getsize(input_path)} байт")
        except Exception as e:
            await status_message.edit_text(f"❌ Ошибка скачивания: {str(e)}")
            await state.clear()
            return

        # Обрабатываем видео
        await status_message.edit_text(f"⚙️ Обрабатываю видео...\n🤔 Генерирую текст на тему: '{theme}'")

        # Используем asyncio.to_thread для блокирующих операций
        success, result_msg, title, desc, used_theme = await asyncio.to_thread(
            process_single_video,
            input_path,
            output_path,
            theme
        )

        if not success:
            await status_message.edit_text(f"❌ {result_msg}")
            await state.clear()
            return

        # Проверяем результат
        if not os.path.exists(output_path):
            await status_message.edit_text("❌ Обработанное видео не создано")
            await state.clear()
            return

        # Отправляем результат
        await status_message.edit_text("📤 Отправляю результат...")

        try:
            # Проверяем длину заголовка для Telegram caption
            if title and len(title) > 1024:  # Ограничение Telegram для caption
                caption = f"🎬 {title[:1021]}...\n\n📌 Тема: {used_theme}"
            else:
                caption = f"🎬 {title}\n\n📌 Тема: {used_theme}"

            # Отправляем видео с заголовком как подпись
            video_file = FSInputFile(output_path, filename=output_filename)
            await message.answer_video(
                video_file,
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

            # Предлагаем обработать еще одно видео
            await message.answer(
                "✅ Готово! Видео обработано успешно.\n\n"
                "Хочешь обработать еще одно видео?\n"
                "1. Отправь новую тему для текста\n"
                "2. Или просто отправь следующее видео - будет использована стандартная тема\n\n"
                "Для отмены используй /cancel"
            )

            # Возвращаемся в состояние ожидания темы
            await state.set_state(VideoProcessing.waiting_for_theme)

        except Exception as e:
            await status_message.edit_text(f"❌ Ошибка отправки: {str(e)}")
            logging.error(f"Ошибка отправки: {e}")
            await state.clear()

    except Exception as e:
        logging.error(f"Ошибка в handle_video: {e}")
        try:
            await message.answer(f"❌ Произошла ошибка: {str(e)}")
        except (TelegramAPIError, TelegramNetworkError) as telegram_error:
            logging.error(f"Не удалось отправить сообщение об ошибке: {telegram_error}")
        except Exception as e:
            logging.error(f"Неожиданная ошибка при отправке сообщения: {e}")

        await state.clear()

    finally:
        # Очистка временных файлов
        try:
            if 'input_path' in locals() and os.path.exists(input_path):
                os.remove(input_path)
            if 'output_path' in locals() and os.path.exists(output_path):
                os.remove(output_path)
        except Exception as e:
            logging.error(f"Ошибка при очистке файлов: {e}")


# Обработка видео БЕЗ предварительного выбора темы (используется стандартная тема)
@dp.message(F.video)
async def handle_video_without_theme(message: Message, state: FSMContext):
    current_state = await state.get_state()

    # Если мы в состоянии waiting_for_video, то пропускаем этот хендлер
    # (далее сработает handle_video_with_theme)
    if current_state == VideoProcessing.waiting_for_video:
        return

    # Используем стандартную тему
    standard_theme = AI_STANDARD_THEME

    await message.answer(
        f"🎬 Видео получено. Использую стандартную тему: '{standard_theme}'\n\n"
        f"⏳ Начинаю обработку...\n\n"
        f"ℹ️ Если хотите задать свою тему, сначала отправьте текст темы, а затем видео"
    )

    # Устанавливаем состояние обработки
    await state.set_state(VideoProcessing.processing)

    input_path = None
    output_path = None

    try:
        # Создаем рабочие папки
        os.makedirs(VIDEOS_FOLDER, exist_ok=True)
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        # Получаем информацию о файле
        video = message.video
        file_info = await bot.get_file(video.file_id)

        # Генерируем уникальные имена файлов
        user_id = message.from_user.id
        timestamp = int(asyncio.get_event_loop().time())
        input_filename = f"temp_{user_id}_{timestamp}.mp4"
        output_filename = f"processed_{user_id}_{timestamp}.mp4"

        input_path = os.path.join(VIDEOS_FOLDER, input_filename)
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        logging.info(f"Скачиваю видео в: {input_path}")
        logging.info(f"Использую стандартную тему: {standard_theme}")

        # Скачиваем видео
        status_message = await message.answer("📥 Скачиваю видео...")
        try:
            await bot.download_file(file_info.file_path, input_path)
            if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                raise Exception("Файл не скачался или пустой")
            logging.info(f"Файл скачан. Размер: {os.path.getsize(input_path)} байт")
        except Exception as e:
            await status_message.edit_text(f"❌ Ошибка скачивания: {str(e)}")
            await state.clear()
            return

        # Обрабатываем видео
        await status_message.edit_text(f"⚙️ Обрабатываю видео...\n🤔 Генерирую текст на стандартную тему...")

        # Используем asyncio.to_thread для блокирующих операций
        success, result_msg, title, desc, used_theme = await asyncio.to_thread(
            process_single_video,
            input_path,
            output_path,
            standard_theme
        )

        if not success:
            await status_message.edit_text(f"❌ {result_msg}")
            await state.clear()
            return

        # Проверяем результат
        if not os.path.exists(output_path):
            await status_message.edit_text("❌ Обработанное видео не создано")
            await state.clear()
            return

        # Отправляем результат
        await status_message.edit_text("📤 Отправляю результат...")

        try:
            # Проверяем длину заголовка для Telegram caption
            if title and len(title) > 1024:  # Ограничение Telegram для caption
                caption = f"🎬 {title[:1021]}...\n\n📌 Тема: {used_theme}"
            else:
                caption = f"🎬 {title}\n\n📌 Тема: {used_theme}"

            # Отправляем видео с заголовком как подпись
            video_file = FSInputFile(output_path, filename=output_filename)
            await message.answer_video(
                video_file,
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

            # Предлагаем обработать еще одно видео
            await message.answer(
                "✅ Готово! Видео обработано успешно.\n\n"
                "Хочешь обработать еще одно видео?\n"
                "1. Отправь новую тему для текста\n"
                "2. Или просто отправь следующее видео - будет использована стандартная тема\n\n"
                "Для отмены используй /cancel"
            )

            # Возвращаемся в состояние ожидания темы
            await state.set_state(VideoProcessing.waiting_for_theme)

        except Exception as e:
            await status_message.edit_text(f"❌ Ошибка отправки: {str(e)}")
            logging.error(f"Ошибка отправки: {e}")
            await state.clear()

    except Exception as e:
        logging.error(f"Ошибка в handle_video: {e}")
        try:
            await message.answer(f"❌ Произошла ошибка: {str(e)}")
        except (TelegramAPIError, TelegramNetworkError) as telegram_error:
            logging.error(f"Не удалось отправить сообщение об ошибке: {telegram_error}")
        except Exception as e:
            logging.error(f"Неожиданная ошибка при отправке сообщения: {e}")

        await state.clear()

    finally:
        # Очистка временных файлов
        try:
            if 'input_path' in locals() and os.path.exists(input_path):
                os.remove(input_path)
            if 'output_path' in locals() and os.path.exists(output_path):
                os.remove(output_path)
        except Exception as e:
            logging.error(f"Ошибка при очистке файлов: {e}")


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