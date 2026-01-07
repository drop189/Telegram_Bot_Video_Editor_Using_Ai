import os

from dotenv import load_dotenv

# Настройка окружения
load_dotenv()

# ============ НАСТРОЙКИ ============
VIDEOS_FOLDER = os.getenv("VIDEOS_FOLDER", "/tmp/videos/input")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "/tmp/videos/output")
VOLUME_PATH = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
FONT_PATH = os.getenv("FONT_PATH", "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

ENVIRONMENT = os.environ.get('RAILWAY_ENVIRONMENT_NAME', "")

# Настройка администраторов и пользователей
admin_ids_str = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()] if admin_ids_str else []  # ID Админов
SUBSCRIBED_USERS_FILE = os.path.join(VOLUME_PATH, "users.json")  # Файл для сохранения пользователей
SUBSCRIBED_USERS = set()  # Глобальная переменная для хранения подписчиков
