import asyncio
import logging
import os
import sys

from bot.dispatcher import dp, bot
from handlers.admin import router as admin_router
from handlers.basic import router as basic_router
from handlers.callbacks import router as callbacks_router
from handlers.processor import router as processor_router
from services.subscribers import load_subscribed_users, send_bot_started_notification
from settings.config import VIDEOS_FOLDER, OUTPUT_FOLDER, SUBSCRIBED_USERS
from settings.logging import setup_logging
from utils.shutdown import graceful_shutdown
from utils.system import check_system_dependencies


# ============ ЗАПУСК БОТА ============

async def main():
    logging.info("Запуск бота...")

    # Регистрация роутеров
    dp.include_router(basic_router)
    dp.include_router(admin_router)
    dp.include_router(callbacks_router)
    dp.include_router(processor_router)

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
        logger = setup_logging()
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
