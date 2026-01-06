import os
import sys
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка окружения
load_dotenv()

# ============ НАСТРОЙКИ ============
VIDEOS_FOLDER = os.getenv("VIDEOS_FOLDER", "/tmp/videos/input")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "/tmp/videos/output")
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
VOLUME_PATH = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Настройка администраторов и пользователей
admin_ids_str = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()] if admin_ids_str else []  # ID пользователя Telegram
SUBSCRIBED_USERS_FILE = os.path.join(VOLUME_PATH, "users.json")  # Файл для сохранения пользователей
SUBSCRIBED_USERS = set()  # Глобальная переменная для хранения подписчиков

# Настройка логирования
env = os.environ.get('RAILWAY_ENVIRONMENT_NAME', "")
level = logging.INFO if env == "production" else logging.DEBUG

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


# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

