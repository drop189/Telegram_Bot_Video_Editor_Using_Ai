import sys
import logging

from settings.config import ENVIRONMENT

# Настройка логирования
level = logging.INFO if ENVIRONMENT == "production" else logging.DEBUG

logger = logging.getLogger()
logger.setLevel(level)
logger.handlers.clear()

# stdout: DEBUG/INFO/WARNING
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.handlers[-1].setLevel(level)
logger.handlers[-1].addFilter(lambda r: r.levelno < logging.ERROR)
logger.handlers[-1].setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# stderr: ERROR/CRITICAL
logger.addHandler(logging.StreamHandler(sys.stderr))
logger.handlers[-1].setLevel(logging.ERROR)
logger.handlers[-1].setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
