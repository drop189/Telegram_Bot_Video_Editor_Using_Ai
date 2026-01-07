import datetime
import logging
import os

from aiogram import types, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import Message
from aiogram.utils.markdown import hbold, hcode

from bot.dispatcher import bot
from bot.states import AdminSendMessage
from services.stats_service import usage_stats, create_activity_chart
from services.subscribers import save_subscribed_users
from settings.config import ADMIN_IDS, VIDEOS_FOLDER, OUTPUT_FOLDER, SUBSCRIBED_USERS
from settings.logging import self_logger

router = Router()


# ============ КОМАНДЫ АДМИНА БОТА ============

# Команда /stat - статистика
@router.message(Command("stat"))
@self_logger
async def cmd_stat(message: Message):
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

    stat_text = f"""
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
        stat_text += f"  {i}. ID: {uid}\n"

    await message.answer(stat_text)


# Команда /stats - красивая статистика
@router.message(Command("stats"))
@self_logger
async def cmd_stats(message: Message):
    """Расширенная статистика бота"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для просмотра статистики.")
        return

    try:
        # Обновляем аптайм
        usage_stats.update_uptime()

        # Получаем данные
        today = datetime.datetime.today().strftime('%Y-%m-%d')
        daily_count = usage_stats.stats['daily_usage'].get(today, 0)
        daily_errors = usage_stats.stats['daily_errors'].get(today, 0)

        # Топ пользователей и тем
        top_users = usage_stats.get_top_users(5)
        top_themes = usage_stats.get_top_themes(5)

        # Среднее время обработки
        avg_time = usage_stats.get_average_processing_time()
        success_rate = usage_stats.get_success_rate()

        # Статистика за 7 дней
        weekly_stats = usage_stats.get_daily_stats(7)

        # Форматируем текст
        stats_text = (
            f"{hbold('📊 СТАТИСТИКА БОТА')}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

            f"{hbold('⏱️  ВРЕМЯ РАБОТЫ:')}\n"
            f"  • Запущен: {usage_stats.stats['start_time'][:16]}\n"
            f"  • Аптайм: {usage_stats.stats['uptime_days']} дней\n"
            f"  • Сессий: {usage_stats.stats['sessions']}\n"
            f"  • Активность: {usage_stats.stats['last_activity'][:19] if usage_stats.stats['last_activity'] else 'нет'}\n\n"

            f"{hbold('📈 ОБРАБОТКА ВИДЕО:')}\n"
            f"  • Всего: {usage_stats.stats['videos_processed']}\n"
            f"  • Успешно: {success_rate:.1f}%\n"
            f"  • Ошибок: {usage_stats.stats['total_errors']}\n"
            f"  • Ср. время: {avg_time:.1f} сек.\n\n"

            f"{hbold('📅 СЕГОДНЯ:')}\n"
            f"  • Запросов: {daily_count}\n"
            f"  • Ошибок: {daily_errors}\n\n"

            f"{hbold('👥 ТОП ПОЛЬЗОВАТЕЛЕЙ:')}\n"
        )

        # Топ пользователей
        for i, (user_id, count) in enumerate(top_users, 1):
            stats_text += f"  {i}. ID {user_id}: {count} запр.\n"

        stats_text += f"\n{hbold('🎯 ПОПУЛЯРНЫЕ ТЕМЫ:')}\n"

        # Топ тем
        for i, (theme, count) in enumerate(top_themes, 1):
            theme_display = theme[:20] + "..." if len(theme) > 20 else theme
            stats_text += f"  {i}. {theme_display}: {count}\n"

        # Пиковые часы
        if usage_stats.stats['peak_hours']:
            peak_hour, peak_count = max(
                usage_stats.stats['peak_hours'].items(),
                key=lambda x: x[1]
            )
            stats_text += f"\n{hbold('⏰ ПИКОВЫЙ ЧАС:')} {peak_hour}:00 ({peak_count} запр.)\n"

        # Последние пользователи
        if usage_stats.stats['last_users']:
            stats_text += f"\n{hbold('🔄 ПОСЛЕДНИЕ ПОЛЬЗОВАТЕЛИ:')}\n"
            for i, uid in enumerate(usage_stats.stats['last_users'][:5], 1):
                stats_text += f"  {i}. ID: {hcode(uid)}\n"

        # Создаем график активности
        if sum(weekly_stats['usage']) > 0:
            chart = await create_activity_chart(weekly_stats)
            await message.answer_photo(
                BufferedInputFile(chart, filename="stats_chart.png"),
                caption=stats_text,
                parse_mode='HTML'
            )
        else:
            await message.answer(stats_text, parse_mode='HTML')

    except Exception as e:
        logging.error(f"Ошибка получения статистики: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")


# Команда /detailed_stats - детальная статистика
@router.message(Command("detailed_stats"))
@self_logger
async def cmd_detailed_stats(message: Message):
    """Детальная статистика"""
    if message.from_user.id not in ADMIN_IDS:
        return

    # Полная информация об ошибках
    error_types = usage_stats.stats.get('error_types', {})

    text = f"{hbold('🔍 ДЕТАЛЬНАЯ СТАТИСТИКА ОШИБОК')}\n\n"

    if error_types:
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            text += f"• {error_type}: {count}\n"
    else:
        text += "Нет данных об ошибках\n"

    # Информация о времени обработки
    if usage_stats.stats['processing_times']:
        times = usage_stats.stats['processing_times']
        text += f"\n{hbold('⏱️  ВРЕМЯ ОБРАБОТКИ:')}\n"
        text += f"• Минимум: {min(times):.1f} сек.\n"
        text += f"• Максимум: {max(times):.1f} сек.\n"
        text += f"• Медиана: {sorted(times)[len(times) // 2]:.1f} сек.\n"

    await message.answer(text, parse_mode='HTML')


# Команда /msg - отправка сообщений с удобным меню
@router.message(Command("msg"))
@self_logger
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
@self_logger
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
@self_logger
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


@router.message(Command("admin"))
@self_logger
async def cmd_admin_menu(message: Message):
    """Меню админ-команд с инлайн-кнопками"""
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для доступа к админ-панели.")
        return

    # Создаем клавиатуру
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="📊 Базовая статистика", callback_data="admin_stat"),
            types.InlineKeyboardButton(text="📈 Расширенная статистика", callback_data="admin_stats")
        ],
        [
            types.InlineKeyboardButton(text="🔍 Детальная статистика", callback_data="admin_detailed_stats"),
            types.InlineKeyboardButton(text="📤 Отправить сообщение", callback_data="admin_send_msg")
        ],
        [
            types.InlineKeyboardButton(text="👤 Добавить пользователя", callback_data="admin_add_user"),
            types.InlineKeyboardButton(text="📨 Быстрая отправка", callback_data="admin_quick_send")
        ],
        [
            types.InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="admin_refresh_stats"),
            types.InlineKeyboardButton(text="🗑️ Очистить кэш", callback_data="admin_clear_cache")
        ],
        [
            types.InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings"),
            types.InlineKeyboardButton(text="❓ Помощь", callback_data="admin_help")
        ]
    ])

    admin_count = len(ADMIN_IDS)
    user_count = len(SUBSCRIBED_USERS)

    welcome_text = (
        f"👑 *Админ-панель*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        f"👤 *Ваш ID:* `{user_id}`\n"
        f"👥 *Пользователей:* {user_count}\n"
        f"👑 *Админов:* {admin_count}\n"
        f"🕐 *Время:* {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"*Выберите действие:*"
    )

    await message.answer(welcome_text, parse_mode='Markdown', reply_markup=keyboard)

@router.message(Command("settings"))
@self_logger
async def cmd_admin_settings(message: Message):
    """Настройки админ-панели"""
    settings_text = (
        f"⚙️ *Настройки админ-панели*\n\n"
        f"📁 *Папки:*\n"
        f"• Видео: `{VIDEOS_FOLDER}`\n"
        f"• Результаты: `{OUTPUT_FOLDER}`\n\n"
        f"👑 *Админы:* {len(ADMIN_IDS)}\n"
        f"👥 *Пользователи:* {len(SUBSCRIBED_USERS)}\n\n"
        f"📊 *Статистика:*\n"
        f"• Обработано видео: {usage_stats.stats.get('videos_processed', 0)}\n"
        f"• Ошибок: {usage_stats.stats.get('total_errors', 0)}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить пути", callback_data="admin_update_paths"),
            InlineKeyboardButton(text="📋 Список админов", callback_data="admin_list_admins")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")
        ]
    ])

    await message.answer(settings_text, parse_mode='Markdown', reply_markup=keyboard)


@router.message(Command("help"))
@self_logger
async def cmd_admin_help(message: Message):
    """Справка по админ-командам"""
    if message.from_user.id not in ADMIN_IDS:
        return

    help_text = (
        f"❓ *Справка по админ-командам*\n\n"
        f"*Основные команды:*\n"
        f"• `/admin` - это меню\n"
        f"• `/stat` - базовая статистика\n"
        f"• `/stats` - расширенная статистика\n"
        f"• `/detailed_stats` - детальная статистика\n\n"
        f"*Работа с пользователями:*\n"
        f"• `/msg` - меню отправки сообщений\n"
        f"• `/send <ID> <текст>` - быстрая отправка\n"
        f"• `/adduser <ID>` - добавить пользователя\n"
        f"• `/users` - список всех пользователей\n\n"
        f"*Системные команды:*\n"
        f"• `/restart` - перезапуск бота\n"
        f"• `/logs` - просмотр логов\n"
        f"• `/clean` - очистка временных файлов"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"),
            InlineKeyboardButton(text="📖 Все команды", callback_data="admin_all_commands")
        ]
    ])

    await message.answer(help_text, parse_mode='Markdown', reply_markup=keyboard)

@router.message(Command("clear"))
@self_logger
async def cmd_clear_temp_files(message):

    pass