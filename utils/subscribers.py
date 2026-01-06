import asyncio
import json
import logging
import os
from config import SUBSCRIBED_USERS_FILE, SUBSCRIBED_USERS, ADMIN_IDS, bot


# ============ ФУНКЦИИ ДЛЯ ПОДПИСЧИКОВ ============

# Подгрузка пользователей бота
def load_subscribed_users():
    """Загружаем список подписчиков из файла"""
    try:
        if os.path.exists(SUBSCRIBED_USERS_FILE):
            with open(SUBSCRIBED_USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logging.info(f"Загружено из {SUBSCRIBED_USERS_FILE}")
                return set(data.get('user_ids', []))
    except Exception as e:
        logging.error(f"Ошибка загрузки пользователей: {e}")
    return set()


# Сохранение ID пользователей
def save_subscribed_users():
    """Сохраняем список пользователей в файл"""
    try:
        with open(SUBSCRIBED_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'user_ids': list(SUBSCRIBED_USERS)}, f, ensure_ascii=False, indent=2)
            logging.info(f"Список пользователей успешно сохранен. Кол-во - {len(SUBSCRIBED_USERS)}")
            logging.info(f"Сохранено в {SUBSCRIBED_USERS_FILE}")
    except Exception as e:
        logging.error(f"Ошибка сохранения пользователей: {e}")


# Отправка сообщения всем пользователям
async def broadcast_message(text: str, only_admins: bool = False):
    """Отправка сообщения всем подписчикам"""
    recipients = ADMIN_IDS if only_admins else SUBSCRIBED_USERS
    sent_count = 0
    failed_count = 0

    for user_id in recipients:
        try:
            await bot.send_message(user_id, text)
            sent_count += 1
            await asyncio.sleep(0.05)  # Небольшая задержка
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            failed_count += 1

    return sent_count, failed_count


# Уведомление о запуске работы
async def send_bot_started_notification():
    """Отправляем уведомление о запуске бота"""
    try:
        text = "✅ Бот запущен и готов к работе!\n\nТеперь вы можете отправлять видео для обработки."
        sent, failed = await broadcast_message(text)
        logging.info(f"Уведомление о запуске отправлено: {sent} успешно, {failed} неудачно")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления о запуске: {e}")


# Уведомление об остановке работы
async def send_bot_stopping_notification():
    try:
        text = "🛑 Бот завершает работу. Все текущие операции будут прерваны.\n\nСпасибо за использование!"
        sent, failed = await broadcast_message(text)
        logging.info(f"Уведомление о завершении отправлено: {sent} успешно, {failed} неудачно")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления о завершении: {e}")

# Уведомление за 30 секунд до остановки работы (не используется)
async def notify_planned_shutdown():
    """Отправляем уведомление об остановке бота"""
    try:
        text = "⏸️ Бот будет отключен через 30 секунд для технических работ.\n\nПожалуйста, завершите текущие операции."
        sent, failed = await broadcast_message(text)
        logging.info(f"Уведомление об остановке отправлено: {sent} успешно, {failed} неудачно")
        await asyncio.sleep(30)
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления об остановке: {e}")