import os

from aiogram import types, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.dispatcher import bot
from bot.states import AdminSendMessage
from services.subscribers import save_subscribed_users
from settings.config import ADMIN_IDS, VIDEOS_FOLDER, OUTPUT_FOLDER, SUBSCRIBED_USERS

router = Router()


# ============ КОМАНДЫ АДМИНА БОТА ============

# Команда /stats - статистика
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика бота (только для админов)"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для просмотра статистики.")
        return

    # Проверяем размер папок
    input_size = 0
    output_size = 0

    if os.path.exists(VIDEOS_FOLDER):
        for root, dirs, files in os.walk(VIDEOS_FOLDER):
            for file in files:
                input_size += os.path.getsize(os.path.join(root, file))

    if os.path.exists(OUTPUT_FOLDER):
        for root, dirs, files in os.walk(OUTPUT_FOLDER):
            for file in files:
                output_size += os.path.getsize(os.path.join(root, file))

    stats_text = f"""
📊 Статистика бота:

👥 Всего пользователей: {len(SUBSCRIBED_USERS)}
👑 Администраторов: {len(ADMIN_IDS)}
    
📁 Папка видео:
  • Путь: {VIDEOS_FOLDER}
  • Размер: {input_size / (1024 * 1024):.2f} MB
    
💾 Папка результатов:
  • Путь: {OUTPUT_FOLDER}
  • Размер: {output_size / (1024 * 1024):.2f} MB
    
🔄 Последние 5 пользователей:
"""

    # Получаем последних 5 пользователей
    recent_users = list(SUBSCRIBED_USERS)[-5:] if SUBSCRIBED_USERS else []
    for i, uid in enumerate(recent_users, 1):
        stats_text += f"  {i}. ID: {uid}\n"

    await message.answer(stats_text)


# Команда /msg - отправка сообщений с удобным меню
@router.message(Command("msg"))
async def cmd_send_message_menu(message: Message, state: FSMContext):
    """Меню отправки сообщения (только для админов)"""
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для отправки сообщений.")
        return

    if not SUBSCRIBED_USERS:
        await message.answer("📭 Список пользователей пуст.")
        return

    # Создаем клавиатуру с пользователями
    users_list = list(SUBSCRIBED_USERS)[:50]  # Ограничиваем 50 пользователями
    keyboard = []

    # Группируем по 2 пользователя в ряд
    for i in range(0, len(users_list), 2):
        row = []
        for j in range(2):
            if i + j < len(users_list):
                user_id_btn = users_list[i + j]
                row.append(types.InlineKeyboardButton(
                    text=f"👤 {user_id_btn}",
                    callback_data=f"send_to_{user_id_btn}"
                ))
        keyboard.append(row)

    # Добавляем кнопки для массовой рассылки
    keyboard.append([
        types.InlineKeyboardButton(text="📢 Всем пользователям", callback_data="send_to_all"),
        types.InlineKeyboardButton(text="👑 Только админам", callback_data="send_to_admins")
    ])

    keyboard.append([
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="send_to_cancel")
    ])

    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(
        "👥 Выберите получателя сообщения:\n\n"
        f"Всего пользователей: {len(SUBSCRIBED_USERS)}",
        reply_markup=reply_markup
    )
    await state.set_state(AdminSendMessage.waiting_for_user_choice)


# Команда /send - отправка сообщения
@router.message(Command("send"))
async def cmd_quick_message(message: Message):
    """Быстрая отправка сообщения"""
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        return

    # Формат: /send ID_пользователя текст_сообщения
    args = message.text.split(maxsplit=2)

    if len(args) < 3:
        await message.answer(
            "Использование: /send <ID> <текст>\n"
            "Пример: /send 777111000 Привет!"
        )
        return

    try:
        target_id = int(args[1])
        send_text = args[2]

        await bot.send_message(target_id, f"{send_text}")
        await message.answer(f"✅ Сообщение отправлено пользователю {target_id}")

    except ValueError:
        await message.answer("❌ ID должен быть числом")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


# Команда /adduser - добавление пользователя
@router.message(Command("adduser"))
async def cmd_add_user(message: Message):
    """Добавить пользователя в users.json"""
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        return

    # Формат: /adduser ID
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer(
            "Использование: /adduser <ID>\n"
            "Пример: /adduser 777111000"
        )
        return

    try:
        target_id = int(args[1])

        if target_id not in SUBSCRIBED_USERS:
            SUBSCRIBED_USERS.add(target_id)
            save_subscribed_users()
            await message.answer(f"✅ Пользователь {target_id} добавлен")
        else:
            await message.answer(f"ℹ️ Пользователь {target_id} уже есть в списке")

    except ValueError:
        await message.answer("❌ ID должен быть числом")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
