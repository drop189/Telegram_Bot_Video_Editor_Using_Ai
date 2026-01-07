import logging

from bot.dispatcher import dp, bot
from services.subscribers import save_subscribed_users, send_bot_stopping_notification


# ============ GRACEFUL SHUTDOWN ============

async def graceful_shutdown():
    """Плавное завершение работы бота"""
    logging.info("Начинаю плавное завершение работы...")

    try:
        # Отправляем уведомление об остановке только если бот работал
        await send_bot_stopping_notification()
    finally:
        # Останавливаем диспетчер
        try:
            await dp.storage.close()
        except Exception as e:
            logging.error(f"Ошибка при закрытии storage: {e}")

        # Сохраняем пользователей
        save_subscribed_users()
        logging.info("Список пользователей сохранен")

        # Закрываем сессию бота
        try:
            await bot.session.close()
        except Exception as e:
            logging.error(f"Ошибка при закрытии сессии бота: {e}")

        logging.info("Бот успешно завершил работу")
