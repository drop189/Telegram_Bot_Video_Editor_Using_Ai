import sys
import logging

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
