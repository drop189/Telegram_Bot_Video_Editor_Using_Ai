import asyncio
import logging
import os
import sys

from config import bot, VIDEOS_FOLDER, OUTPUT_FOLDER, dp, \
    SUBSCRIBED_USERS
from utils.subscribers import save_subscribed_users, load_subscribed_users, send_bot_stopping_notification, \
    send_bot_started_notification
from utils.system import check_system_dependencies


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


# ============ ЗАПУСК БОТА ============

async def main():
    logging.info("Запуск бота...")

    # Загружаем подписчиков
    SUBSCRIBED_USERS.update(load_subscribed_users())
    logging.info(f"Загружено {len(SUBSCRIBED_USERS)} подписчиков")

    # Создаем необходимые папки
    os.makedirs(VIDEOS_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    try:
        # Отправляем уведомление о запуске
        await send_bot_started_notification()

        # Удаляем вебхуки и начинаем поллинг
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logging.info("Получен сигнал KeyboardInterrupt")
    except Exception as e:
        logging.error(f"Критическая ошибка при запуске бота: {e}")
    finally:
        # Всегда выполняем graceful shutdown
        await graceful_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
        logging.info("Запуск бота на Railway...")

        if not check_system_dependencies():
            logging.error("Критические зависимости отсутствуют. Завершение работы.")
            sys.exit(1)

        # Запускаем бота
        logging.info("Все зависимости доступны. Запускаю бота...")
    except KeyboardInterrupt:
        print("\nБот выключен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
