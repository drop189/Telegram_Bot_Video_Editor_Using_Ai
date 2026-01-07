import asyncio
import logging

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot.dispatcher import bot
from bot.states import AdminSendMessage
from handlers.admin import cmd_admin_menu, cmd_stats, cmd_detailed_stats, cmd_stat, \
    cmd_admin_help, cmd_admin_settings, cmd_clear_temp_files
from services.stats_service import usage_stats
from settings.config import ADMIN_IDS, SUBSCRIBED_USERS
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

    # Сразу отвечаем на callback
    await callback.answer()

    # Сохраняем ID сообщения для удаления
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id

    if action == "stat":
        await cmd_stat(callback.message, flag=True)
        await delete_message(callback.bot, chat_id, message_id)

    elif action == "stats":
        await cmd_stats(callback.message)
        await delete_message(callback.bot, chat_id, message_id)

    elif action == "detailed_stats":
        await cmd_detailed_stats(callback.message)
        await delete_message(callback.bot, chat_id, message_id)

    elif action == "send_msg":
        # Для меню отправки не удаляем сообщение, а редактируем
        await edit_to_send_menu(callback, state)

    elif action == "add_user":
        await callback.message.answer(
            "👤 *Добавление пользователя*\n\n"
            "Используйте команду:\n"
            "`/adduser <ID_пользователя>`\n\n"
            "*Пример:* `/adduser 123456789`",
            parse_mode='Markdown'
        )
        await delete_message(callback.bot, chat_id, message_id)

    elif action == "quick_send":
        await callback.message.answer(
            "📨 *Быстрая отправка сообщения*\n\n"
            "Используйте команду:\n"
            "`/send <ID_пользователя> <текст>`\n\n"
            "*Пример:* `/send 123456789 Привет!`",
            parse_mode='Markdown'
        )
        await delete_message(callback.bot, chat_id, message_id)

    elif action == "refresh_stats":
        if hasattr(usage_stats, '_cache'):
            usage_stats._cache = None
        await callback.message.answer("✅ Кэш статистики очищен!")
        await cmd_stats(callback.message)
        await delete_message(callback.bot, chat_id, message_id)

    elif action == "clear_cache":
        await cmd_clear_temp_files(callback.message)
        await delete_message(callback.bot, chat_id, message_id)

    elif action == "settings":
        await cmd_admin_settings(callback.message)
        await delete_message(callback.bot, chat_id, message_id)

    elif action == "help":
        await cmd_admin_help(callback.message)
        await delete_message(callback.bot, chat_id, message_id)

    elif action == "back":
        await cmd_admin_menu(callback.message)
        await delete_message(callback.bot, chat_id, message_id)

async def delete_message(bott, chat_id: int, message_id: int):
    """Безопасное удаление сообщения"""
    try:
        await bott.delete_message(chat_id, message_id)
    except Exception as e:
        logging.debug(f"Не удалось удалить сообщение: {e}")

async def edit_to_send_menu(callback: CallbackQuery, state: FSMContext):
    """Редактирует сообщение в меню отправки"""
    if not SUBSCRIBED_USERS:
        await callback.message.edit_text("📭 Список пользователей пуст.")
        return

    users_list = list(SUBSCRIBED_USERS)[:50]
    keyboard = []

    for i in range(0, len(users_list), 2):
        row = []
        for j in range(2):
            if i + j < len(users_list):
                user_id_btn = users_list[i + j]
                row.append(InlineKeyboardButton(
                    text=f"👤 {user_id_btn}",
                    callback_data=f"admin_send_to_{user_id_btn}"
                ))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton(text="📢 Всем пользователям", callback_data="admin_send_to_all"),
        InlineKeyboardButton(text="👑 Только админам", callback_data="admin_send_to_admins")
    ])

    keyboard.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")
    ])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        "👥 *Выберите получателя сообщения:*\n\n"
        f"Всего пользователей: {len(SUBSCRIBED_USERS)}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

    await state.set_state(AdminSendMessage.waiting_for_user_choice)
