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
    """Декоратор для логирования ошибок в хендлерах"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        message = None

        # Ищем объект message
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
            user_id = message.from_user.id if message else 0
            error_type = type(e).__name__
            error_msg = str(e)

            # Получаем логгер
            logger = logging.getLogger(func.__module__)

            # Детальное логирование
            logger.error(
                f"Ошибка в {func.__name__} | "
                f"Пользователь: {user_id} | "
                f"Тип: {error_type} | "
                f"Сообщение: {error_msg[:200]}",
                exc_info=True,
                extra={
                    'user_id': user_id,
                    'handler': func.__name__,
                    'error_type': error_type,
                    'module': func.__module__
                }
            )

            # Запись в статистику
            try:
                usage_stats.record_error(
                    user_id=user_id,
                    error_type=error_type,
                    error_message=error_msg[:200]
                )
            except Exception as stats_error:
                logger.error(f"Ошибка записи статистики: {stats_error}")

            # НЕ ПОДНИМАЕМ ИСКЛЮЧЕНИЕ для хендлеров
            # Вместо этого пытаемся отправить сообщение пользователю
            if message and hasattr(message, 'answer'):
                try:
                    await message.answer(
                        f"❌ Произошла ошибка: {error_msg[:100]}" +
                        ("..." if len(error_msg) > 100 else "")
                    )
                except Exception:
                    pass

            return None  # Возвращаем None вместо исключения

    return wrapper
