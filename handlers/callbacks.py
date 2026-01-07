import asyncio
import logging

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot.dispatcher import bot
from bot.states import AdminSendMessage
from handlers.admin import cmd_admin_menu, cmd_stats, cmd_send_message_menu, cmd_detailed_stats, cmd_stat, \
    cmd_admin_help, cmd_admin_settings, cmd_clear_temp_files
from services.stats_service import usage_stats
from settings.config import ADMIN_IDS, SUBSCRIBED_USERS, VIDEOS_FOLDER, OUTPUT_FOLDER
from settings.logging import self_logger

router = Router()


# ============ КОЛБЭКИ ============

# Обработка ответов от кнопок из бота
@router.callback_query(AdminSendMessage.waiting_for_user_choice, F.data.startswith("send_to_"))
@self_logger
async def process_user_choice(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "send_to_cancel":
        await callback.message.answer("❌ Отменено")
        await callback.message.delete()
        await state.clear()
        return

    # Сохраняем выбор пользователя
    if data == "send_to_all":
        target = "all"
        target_name = "всем пользователям"
    elif data == "send_to_admins":
        target = "admins"
        target_name = "администраторам"
    else:
        user_id = int(data.replace("send_to_", ""))
        target = user_id
        target_name = f"пользователю {user_id}"

    await state.update_data(target=target, target_name=target_name)

    await callback.message.edit_text(
        f"📝 Выбран получатель: {target_name}\n\n"
        "Теперь отправьте текст сообщения:"
    )
    await state.set_state(AdminSendMessage.waiting_for_message_text)
    await callback.answer()


# Реализация выбора кнопок
@router.message(AdminSendMessage.waiting_for_message_text, F.text)
@self_logger
async def process_message_text(message: Message, state: FSMContext):
    data = await state.get_data()
    target = data.get('target')
    target_name = data.get('target_name')
    text_message = message.text

    await state.clear()

    # Определяем получателей
    if target == "all":
        recipients = SUBSCRIBED_USERS
    elif target == "admins":
        recipients = ADMIN_IDS
    else:
        recipients = [target]

    # Отправляем сообщение
    sent_count = 0
    failed_count = 0

    status_msg = await message.answer(f"📤 Отправляю сообщение {target_name}...")

    for user_id in recipients:
        try:
            await bot.send_message(user_id, f"📨 Сообщение от администратора:\n\n{text_message}")
            sent_count += 1
            await asyncio.sleep(0.1)  # Задержка между отправками
        except Exception as e:
            failed_count += 1
            logging.error(f"Ошибка отправки пользователю {user_id}: {e}")

    await status_msg.edit_text(
        f"📊 Результаты отправки:\n\n"
        f"✅ Успешно: {sent_count}\n"
        f"❌ Не удалось: {failed_count}\n"
        f"👥 Получатель: {target_name}"
    )

    # Логируем
    logging.info(f"Админ {message.from_user.id} отправил сообщение {target_name}: {text_message[:50]}...")


@router.callback_query(F.data.startswith("admin_"))
@self_logger
async def handle_admin_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик всех админ-колбэков"""
    user_id = callback.from_user.id

    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Нет прав!", show_alert=True)
        return

    action = callback.data.replace("admin_", "")


    if action == "stat":
        # Вызываем функцию базовой статистики
        await cmd_stat(callback.message)

    elif action == "stats":
        # Вызываем функцию расширенной статистики
        await cmd_stats(callback.message)

    elif action == "detailed_stats":
        # Вызываем функцию детальной статистики
        await cmd_detailed_stats(callback.message)

    elif action == "send_msg":
        # Вызываем меню отправки сообщений
        await cmd_send_message_menu(callback.message, state)

    elif action == "add_user":
        # Показываем инструкцию по добавлению пользователя
        await callback.message.answer(
            "👤 *Добавление пользователя*\n\n"
            "Используйте команду:\n"
            "`/adduser <ID_пользователя>`\n\n"
            "*Пример:* `/adduser 123456789`\n\n"
            "Или введите ID пользователя:",
            parse_mode='Markdown'
        )

    elif action == "quick_send":
        # Показываем инструкцию по быстрой отправке
        await callback.message.answer(
            "📨 *Быстрая отправка сообщения*\n\n"
            "Используйте команду:\n"
            "`/send <ID_пользователя> <текст>`\n\n"
            "*Пример:* `/send 123456789 Привет!`",
            parse_mode='Markdown'
        )

    elif action == "refresh_stats":
        # Инвалидируем кэш статистики
        if hasattr(usage_stats, '_cache'):
            usage_stats._cache = None
        await callback.message.answer("✅ Кэш статистики очищен!")
        # Показываем обновленную статистику
        await cmd_stats(callback.message)

    elif action == "clear_cache":
        # Очистка временных файлов
        await cmd_clear_temp_files(callback.message)

    elif action == "settings":
        await cmd_admin_settings(callback.message)

    elif action == "help":
        await cmd_admin_help(callback.message)

    elif action == "back":
        # Возврат в главное меню
        await cmd_admin_menu(callback.message)

    await callback.message.delete()
    await callback.answer()
