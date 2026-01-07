import functools
import logging
import sys
from typing import Callable

from services.stats_service import usage_stats
from settings.config import ENVIRONMENT


# Настройка логирования
def setup_logging():
    """Настраивает логирование для всего приложения"""
    level = logging.INFO if ENVIRONMENT == "production" else logging.DEBUG

    # Получаем корневой логгер
    logger = logging.getLogger()

    # Удаляем все существующие обработчики
    logger.handlers.clear()

    # Устанавливаем уровень
    logger.setLevel(level)

    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Обработчик для stdout (все кроме ERROR)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.addFilter(lambda record: record.levelno < logging.ERROR)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # Обработчик для stderr (только ERROR и выше)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    # Логируем запуск
    logger.info(f"Логирование настроено. Уровень: {logging.getLevelName(level)}")
    return logger


def self_logger(func: Callable):
    """Декоратор для автоматического логирования ошибок и записи статистики"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Ищем message в аргументах
        message = None
        for arg in args:
            if hasattr(arg, 'from_user'):
                message = arg
                break

        if not message:
            for key, value in kwargs.items():
                if hasattr(value, 'from_user'):
                    message = value
                    break

        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if message:
                user_id = message.from_user.id
                error_type = type(e).__name__
                error_msg = str(e)

                # Записываем в статистику
                usage_stats.record_error(
                    user_id=user_id,
                    error_type=error_type,
                    error_message=error_msg[:200]
                )

                # Логируем
                logger = logging.getLogger(func.__module__)
                logger.error(
                    f"Ошибка в {func.__name__} у пользователя {user_id}: "
                    f"{error_type} - {error_msg}",
                    exc_info=True
                )

            # Переподнимаем исключение
            raise

    return wrapper
