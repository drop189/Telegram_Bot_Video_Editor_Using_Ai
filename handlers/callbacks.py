import asyncio
import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from config import dp, ADMIN_IDS, SUBSCRIBED_USERS, bot
from states import AdminSendMessage


# ============ КОЛБЭКИ ============

# Обработка ответов от кнопок из бота
@dp.callback_query(AdminSendMessage.waiting_for_user_choice, F.data.startswith("send_to_"))
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
@dp.message(AdminSendMessage.waiting_for_message_text, F.text)
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
