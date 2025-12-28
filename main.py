import os
import sys
import asyncio
import subprocess
import random
import textwrap

import requests
import json
import logging
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage


# ============ НАСТРОЙКИ ============
VIDEOS_FOLDER = os.getenv("VIDEOS_FOLDER", "/tmp/videos/input")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "/tmp/videos/output")
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Настройка администраторов и пользователей
admin_ids_str = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()] if admin_ids_str else []  # ID пользователя Telegram
SUBSCRIBED_USERS_FILE = "users.json"  # Файл для сохранения пользователей

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Глобальная переменная для хранения подписчиков
SUBSCRIBED_USERS = set()

# ============ ADMIN СОСТОЯНИЯ ============
class AdminSendMessage(StatesGroup):
    waiting_for_user_choice = State()
    waiting_for_message_text = State()

# ============ FSM СОСТОЯНИЯ ============
class VideoProcessing(StatesGroup):
    waiting_for_theme = State()
    waiting_for_video = State()
    processing = State()


# Настройка логирования для Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Важно для Railway
    ]
)

def check_system_dependencies():
    """Проверяем системные зависимости"""
    logging.info("=== ПРОВЕРКА СИСТЕМНЫХ ЗАВИСИМОСТЕЙ ===")

    # Проверяем FFmpeg
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logging.info("✅ FFmpeg найден")
            # Получаем версию из вывода
            version_line = result.stdout.split('\n')[0]
            logging.info(f"   Версия: {version_line}")
        else:
            logging.error("❌ FFmpeg не работает корректно")
            return False
    except FileNotFoundError:
        logging.error("❌ FFmpeg не найден в PATH")

        # Пробуем найти альтернативные пути
        possible_paths = [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/bin/ffmpeg",
            "ffmpeg"
        ]

        for path in possible_paths:
            try:
                subprocess.run([path, "-version"],
                               capture_output=True,
                               text=True)
                logging.info(f"✅ FFmpeg найден по пути: {path}")
                return True
            except:
                continue

        return False

    # Проверяем другие команды
    commands_to_check = ["which", "ls", "mkdir", "rm"]
    for cmd in commands_to_check:
        try:
            subprocess.run([cmd, "--version"],
                           capture_output=True,
                           text=True)
            logging.debug(f"✅ {cmd} доступен")
        except:
            logging.warning(f"⚠️  {cmd} не найден")

    logging.info("=== ПРОВЕРКА ЗАВЕРШЕНА ===")
    return True

# ============ ФУНКЦИИ ДЛЯ ПОДПИСЧИКОВ ============
# Подгрузка пользователей бота
def load_subscribed_users():
    """Загружаем список подписчиков из файла"""
    try:
        if os.path.exists(SUBSCRIBED_USERS_FILE):
            with open(SUBSCRIBED_USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
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
    """Отправляем уведомление об остановке бота"""
    try:
        text = "⏸️ Бот будет отключен через 30 секунд для технических работ.\n\nПожалуйста, завершите текущие операции."
        sent, failed = await broadcast_message(text)
        logging.info(f"Уведомление об остановке отправлено: {sent} успешно, {failed} неудачно")
        await asyncio.sleep(30)
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления об остановке: {e}")


# ============ ФУНКЦИИ ОБРАБОТКИ ВИДЕО ============

# Конвертация видео с iPhone
def convert_mov_to_mp4(input_file, output_file):
    """Конвертируем MOV в MP4 через FFmpeg"""
    logging.info(f"Конвертирую {os.path.basename(input_file)}...")
    try:
        cmd = [
            FFMPEG_PATH, '-i', input_file,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y', output_file
        ]

        logging.debug(f"Выполняем команду: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode != 0:
            logging.error(f"FFmpeg ошибка: {result.stderr}")
            return False

        return True
    except Exception as e:
        logging.error(f"Ошибка при конвертации видео: {e}")
        return False


def add_text_with_ffmpeg(input_file, output_file, text):
    """Добавляем текст на видео используя только FFmpeg"""
    logging.info(f"Добавляю текст ({len(text)} символов): '{text}'")

    # Создаем уникальное имя для временного текстового файла
    text_file_name = f"temp_text_{os.getpid()}.txt"

    try:
        # 1. Записываем текст в файл с кодировкой UTF-8
        # Это решает проблемы с кириллицей и символами типа длинного тире
        with open(text_file_name, "w", encoding="utf-8") as f:
            f.write(text)

        # 2. Формируем команду, указывая FFmpeg читать текст из файла
        cmd = [
            FFMPEG_PATH, '-i', input_file,
            '-vf', f"drawtext=textfile='{text_file_name}':"
                   f"fontcolor=black:"
                   f"fontsize=35:"
                   f"box=1:boxcolor=white@1:boxborderw=15:"
                   f"x=(w-text_w)/2:y=h*0.8:"
                   f"line_spacing=10:text_align=center:fix_bounds=true",
            '-c:a', 'copy',
            '-y', output_file
        ]

        # 3. Запускаем процесс
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        if result.returncode != 0:
            logging.error(f"FFmpeg ошибка: {result.stderr}")
            return False

        return True

    except Exception as e:
        logging.error(f"Ошибка при добавлении текста: {e}")
        return False
    finally:
        # 4. Удаляем временный файл
        if os.path.exists(text_file_name):
            os.remove(text_file_name)


def create_rounded_text_image(text, output_path, video_width, video_height, font_path=None, bg_color="white@0.7", text_color="black"):
    """
    Создает PNG с прозрачным фоном, текстом и закругленной подложкой.
    """

    # Максимальная ширина текста (90% от ширины видео, чтобы не влезало в края)
    max_width = int(video_width * 0.9)

    # Размер шрифта (4% от высоты видео)
    font_size = int(video_height * 0.04)
    if font_size < 20: font_size = 20

    # Отступы (отступ текста от края подложки)
    padding_x = int(video_width * 0.02)
    if padding_x < 15: padding_x = 15
    padding_y = 10

    # 2. Загрузка шрифта
    try:
        if font_path and os.path.exists(font_path):
            font = ImageFont.truetype(font_path, font_size)
        else:
            font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()

    # Создаем временное изображение, чтобы замерить размер текста
    temp_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(temp_img)

    # Получаем ширину символа примерно, чтобы посчитать кол-во символов в строке
    avg_char_width = draw.textlength("x", font=font)
    if avg_char_width == 0: avg_char_width = 1 # Защита от деления на ноль
    chars_per_line = int(max_width / avg_char_width)

    # Разбиваем текст на строки, которые влезают в max_width
    lines = textwrap.wrap(text, width=chars_per_line)
    if not lines: lines = [""]

    line_infos = []
    for line in lines:
        # Замеряем размеры строки
        bbox = draw.textbbox((0, 0), line, font=font)
        l_width = bbox[2] - bbox[0]
        l_height = bbox[3] - bbox[1]


        box_width = l_width + (padding_x * 2)
        box_height = l_height + (padding_y * 2)

        # Сохраняем информацию о строке
        line_infos.append({
            "text": line,
            "box_w": box_width,
            "box_h": box_height,
            "bbox": bbox,
            "text_w": l_width,
            "text_h": l_height
        })

    # Находим самую широкую строку, чтобы задать ширину всего изображения
    max_box_width = max(item["box_w"] for item in line_infos)

    # Высота всего изображения = сумма высот всех строк + без отступа
    total_height = sum(item["box_h"] for item in line_infos) + (len(lines) - 1)

    # Создаем итоговое изображение с прозрачностью (RGBA)
    image = Image.new("RGBA", (max_box_width, total_height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    radius = int(font_size / 2)
    current_y = 0

    for item in line_infos:
        box_w = item["box_w"]
        box_h = item["box_h"]
        txt = item["text"]
        bbox = item["bbox"]

        # Вычисляем X, чтобы подложка была по центру общей картинки
        x = (max_box_width - box_w) // 2

        box_center_y = current_y + (box_h / 2)
        text_center_y = (bbox[1] + bbox[3]) / 2
        text_offset_y = text_center_y


        # Рисуем подложку для текущей строки
        draw.rounded_rectangle(
            [(x, current_y), (x + box_w, current_y + box_h)],
            radius=radius,
            fill=bg_color
        )

        # Рисуем текст внутри подложки
        text_x = x + padding_x
        text_y = box_center_y - text_offset_y - (font_size * 0.1)

        draw.text((text_x, text_y), txt, font=font, fill=text_color)

        # Сдвигаем Y для следующей строки
        current_y += box_h

    # Сохраняем
    image.save(output_path)
    return output_path

def add_text_with_rounded_box(input_video, output_video, text, font_path="/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"):
    logging.info("Генерирую подложку с закруглением...")

    # Имя временной картинки
    overlay_path = "temp_rounded_text.png"

    try:

        # 1. Получаем реальные размеры видео
        v_width, v_height = get_video_dimensions(input_video)
        logging.info(f"Размер видео: {v_width}x{v_height}")

        # 2. Генерируем картинку с помощью Python
        create_rounded_text_image(
            text=text,
            output_path=overlay_path,
            video_width=v_width,
            video_height=v_height,
            font_path=font_path,
            bg_color="white",
            text_color="black"
        )

        # 3. Команда FFmpeg для наложения картинки

        offset_bottom = int(v_height * 0.2)
        cmd = [
            FFMPEG_PATH,
            '-i', input_video,
            '-framerate', '25',
            '-i', overlay_path,
            '-filter_complex',
            f"[1:v]format=rgba,colorchannelmixer=aa=1[alpha];[0:v][alpha]overlay=x=(W-w)/2:y=H-h-{offset_bottom},format=yuv420p",
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-c:a', 'copy',
            '-y', output_video
        ]

        logging.debug(f"Команда: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        if result.returncode != 0:
            logging.error(f"FFmpeg ошибка: {result.stderr}")
            return False

        return True

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        return False
    finally:
        # Удаляем временную картинку
        if os.path.exists(overlay_path):
            os.remove(overlay_path)

def get_video_dimensions(video_path):
    """
    Возвращает размеры (width, height) видео.
    """
    cmd = [
        FFMPEG_PATH.replace("ffmpeg", "ffprobe"),
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=s=x:p=0',
        video_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split('x'))
        return width, height
    except Exception as e:
        logging.error(f"Не удалось получить размер видео: {e}")
        # Возвращаем значения по умолчанию (FullHD), если не получилось
        return 1920, 1080

def process_video(input_path, output_path, text):
    """Обрабатываем одно видео"""
    try:
        filename = os.path.basename(input_path)
        logging.info(f"Обрабатываю: {filename}")

        # Проверяем расширение
        temp_file = None
        if filename.lower().endswith('.mov'):
            # Сначала конвертируем MOV во временный MP4
            temp_file = output_path.replace('.mp4', '_temp.mp4')
            if not convert_mov_to_mp4(input_path, temp_file):
                logging.error(f"Ошибка конвертации")
                return False
            input_path = temp_file

        # Добавляем текст
        if add_text_with_rounded_box(input_path, output_path, text):
            logging.info(f"Видео готово")

            # Удаляем временный файл если он был создан
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
            return True
        else:
            logging.error(f"Ошибка добавления текста")
            return False

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        return False


def generate_title_and_description(theme: str):
    """Генерация заголовка и описания через OpenRouter"""
    prompt = f"""
    Ты — философ-практик и мастер с 20-летним стажем в индустрии барберинга и мужского груминга.
    Ты наблюдаешь за салоном, клиентами и инструментами как за метафорой жизни. 
    Твои тексты — это короткие, емкие, визуальные мини-эссе для Instagram Reels. 
    Они сочетают поэзию, практическую мудрость и острые социальные наблюдения. 
    Твой стиль: лаконичный, слегка ироничный, но глубокий. 
    Как смесь Алена де Боттона и крутого барбера с улиц большого города.
    Не повторяйся. Не пиши искусство быть собой.
    На тему только опирайся, строго следуй формату.
    
    ТЕМА:
    {theme}

    СДЕЛАЙ:
    1. Заголовок строго в 1 строку, коротко.
    2. Описание 3–4 абзаца.
    3. Спокойный, зрелый тон.
    4. Без маркетинговых клише.
    5. В конце 7–10 хэштегов.

    ФОРМАТ(СТРОГО!!!):

    ЗАГОЛОВОК:
    строка

    ОПИСАНИЕ:
    текст
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": round(random.uniform(0.65, 0.9), 2)
    }

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=60
        )
        r.raise_for_status()

        content = r.json()["choices"][0]["message"]["content"]

        logging.debug(f"Получен ответ от ИИ:\n{content}")

        if "ОПИСАНИЕ:" in content:
            title_part, desc_part = content.split("ОПИСАНИЕ:")
            title = title_part.replace("ЗАГОЛОВОК:", "").strip()
            description = desc_part.strip()
        else:
            # Если формат не соответствует, возвращаем весь текст нейросети для генерации заголовка
            ar_prompt = f"Отправь короткий заголовок до 5 слов, которым можно описать этот текст: {content}"

            ar_payload = {
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": ar_prompt}],
                "temperature": round(random.uniform(0.65, 0.9), 2)
            }

            ar = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                data=json.dumps(ar_payload),
                timeout=60
            )
            ar.raise_for_status()

            ar_content = ar.json()["choices"][0]["message"]["content"]

            title = ar_content.strip()
            description = content

        logging.info(f"Сгенерирован заголовок: {title}")
        logging.info(f"Сгенерировано описание (первые 100 символов): {description[:100]}...")
        return title, description

    except Exception as e:
        logging.error(f"Ошибка генерации текста: {e}")
        return "Философия барберинга", "Описание не сгенерировано из-за ошибки API."


def process_single_video(input_path, output_path, theme=None):
    """Обработка одного видео для бота"""
    try:
        # Создаем папки если не существуют
        os.makedirs(os.path.dirname(input_path), exist_ok=True)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Проверяем FFmpeg
        try:
            subprocess.run([FFMPEG_PATH, '-version'], capture_output=True, check=True)
        except Exception as e:
            logging.error(f"FFmpeg не найден: {e}")
            return False, "FFmpeg не найден", None, None

        # Если тема не указана, используем стандартную
        if not theme:
            theme = "Философия барберинга, мужской стиль и уход за собой"

        # Генерируем текст
        text, desc = generate_title_and_description(theme)

        # Обрабатываем видео
        if process_video(input_path, output_path, text):
            return True, "Успешно обработано", text, desc, theme
        else:
            return False, "Ошибка обработки видео", text, desc, theme

    except Exception as e:
        logging.error(f"Ошибка в process_single_video: {e}")
        return False, f"Ошибка: {str(e)}", None, None, theme


# ============ КОМАНДЫ БОТА ============

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # Добавляем пользователя в подписчики
    if user_id not in SUBSCRIBED_USERS:
        SUBSCRIBED_USERS.add(user_id)
        save_subscribed_users()
        logging.info(f"Новый пользователь подписался: {user_id} ({username})")

    await message.answer(
        "👋 Привет! Я бот для обработки видео с философскими текстами о барберинге.\n\n"
        "📌 Как это работает:\n"
        "1. Выбери тему для текста (или используй стандартную)\n"
        "2. Отправь видео\n"
        "3. Я добавлю текст на видео и сгенерирую описание\n\n"
        "✏️ Чтобы начать, отправь свою тему для текста (например: 'стиль, уход, профессия')\n"
        "📝 Или просто отправь видео - тогда будет использована стандартная тема\n\n"
        "ℹ️ Теперь вы будете получать уведомления о статусе бота!"
    )
    await state.set_state(VideoProcessing.waiting_for_theme)


# Команда /default - использовать стандартную тему
@dp.message(Command("default"))
async def cmd_default(message: Message, state: FSMContext):
    await state.update_data(theme="Философия барберинга, мужской стиль и уход за собой")
    await message.answer(
        "✅ Использую стандартную тему: 'Философия барберинга, мужской стиль и уход за собой'\n\n"
        "Теперь отправь мне видео для обработки! 🎬"
    )
    await state.set_state(VideoProcessing.waiting_for_video)


# Команда /cancel - отмена
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Операция отменена. Используйте /start чтобы начать заново.")


# ============ КОМАНДЫ АДМИНА БОТА ============
# Команда /stats - статистика
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика бота (только для админов)"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для просмотра статистики.")
        return

    # Проверяем размер папок
    input_size = 0
    output_size = 0

    if os.path.exists(VIDEOS_FOLDER):
        for root, dirs, files in os.walk(VIDEOS_FOLDER):
            for file in files:
                input_size += os.path.getsize(os.path.join(root, file))

    if os.path.exists(OUTPUT_FOLDER):
        for root, dirs, files in os.walk(OUTPUT_FOLDER):
            for file in files:
                output_size += os.path.getsize(os.path.join(root, file))

    stats_text = f"""
📊 Статистика бота:

👥 Всего пользователей: {len(SUBSCRIBED_USERS)}
👑 Администраторов: {len(ADMIN_IDS)}
    
📁 Папка видео:
  • Путь: {VIDEOS_FOLDER}
  • Размер: {input_size / (1024 * 1024):.2f} MB
    
💾 Папка результатов:
  • Путь: {OUTPUT_FOLDER}
  • Размер: {output_size / (1024 * 1024):.2f} MB
    
🔄 Последние 5 пользователей:
"""

    # Получаем последних 5 пользователей
    recent_users = list(SUBSCRIBED_USERS)[-5:] if SUBSCRIBED_USERS else []
    for i, uid in enumerate(recent_users, 1):
        stats_text += f"  {i}. ID: {uid}\n"

    await message.answer(stats_text)

# Команда /msg - отправка сообщений с удобным меню
@dp.message(Command("msg"))
async def cmd_send_message_menu(message: Message, state: FSMContext):
    """Меню отправки сообщения (только для админов)"""
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для отправки сообщений.")
        return

    if not SUBSCRIBED_USERS:
        await message.answer("📭 Список пользователей пуст.")
        return

    # Создаем клавиатуру с пользователями
    users_list = list(SUBSCRIBED_USERS)[:50]  # Ограничиваем 50 пользователями
    keyboard = []

    # Группируем по 2 пользователя в ряд
    for i in range(0, len(users_list), 2):
        row = []
        for j in range(2):
            if i + j < len(users_list):
                user_id_btn = users_list[i + j]
                row.append(types.InlineKeyboardButton(
                    text=f"👤 {user_id_btn}",
                    callback_data=f"send_to_{user_id_btn}"
                ))
        keyboard.append(row)

    # Добавляем кнопки для массовой рассылки
    keyboard.append([
        types.InlineKeyboardButton(text="📢 Всем пользователям", callback_data="send_to_all"),
        types.InlineKeyboardButton(text="👑 Только админам", callback_data="send_to_admins")
    ])

    keyboard.append([
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_send")
    ])

    reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)

    await message.answer(
        "👥 Выберите получателя сообщения:\n\n"
        f"Всего пользователей: {len(SUBSCRIBED_USERS)}",
        reply_markup=reply_markup
    )
    await state.set_state(AdminSendMessage.waiting_for_user_choice)

# Команда /send - отправка сообщения
@dp.message(Command("send"))
async def cmd_quick_message(message: Message):
    """Быстрая отправка сообщения"""
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        return

    # Формат: /send ID_пользователя текст_сообщения
    args = message.text.split(maxsplit=2)

    if len(args) < 3:
        await message.answer(
            "Использование: /send <ID> <текст>\n"
            "Пример: /send 777111000 Привет!"
        )
        return

    try:
        target_id = int(args[1])
        send_text = args[2]

        await bot.send_message(target_id, f"{send_text}")
        await message.answer(f"✅ Сообщение отправлено пользователю {target_id}")

    except ValueError:
        await message.answer("❌ ID должен быть числом")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Команда /admin_send - отправка сообщения, более универсальная команда, уведомления пользователя
@dp.message(Command("admin_send"))
async def cmd_admin_send(message: Message):
    """Универсальная команда отправки сообщения админом"""
    if message.from_user.id not in ADMIN_IDS:
        return

    # Формат: /admin_send ID текст
    parts = message.text.split(maxsplit=2)

    if len(parts) < 3:
        await message.answer("Формат: /admin_send <ID> <текст>")
        return

    try:
        target_id = int(parts[1])
        text = parts[2]

        success, result_msg = await send_message_as_admin(
            target_user_id=target_id,
            message_text=text,
            from_admin_id=message.from_user.id
        )

        if success:
            await message.answer(f"✅ {result_msg}")
        else:
            await message.answer(f"❌ {result_msg}")

    except ValueError:
        await message.answer("❌ ID должен быть числом")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Обработка ответов от кнопок из бота(колбеки)
@dp.callback_query(AdminSendMessage.waiting_for_user_choice, F.data.startswith("send_to_"))
async def process_user_choice(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "cancel_send":
        await callback.message.delete()
        await callback.answer("Отменено")
        await state.clear()
        return

    # Сохраняем выбор пользователя
    if data == "send_to_all":
        target = "all"
        target_name = "всем пользователям"
    elif data == "send_to_admins":
        target = "admins"
        target_name = "администраторам"
    else:
        user_id = int(data.replace("send_to_", ""))
        target = user_id
        target_name = f"пользователю {user_id}"

    await state.update_data(target=target, target_name=target_name)

    await callback.message.edit_text(
        f"📝 Выбран получатель: {target_name}\n\n"
        "Теперь отправьте текст сообщения:"
    )
    await state.set_state(AdminSendMessage.waiting_for_message_text)
    await callback.answer()

# Реализация выбора кнопок(ответы на колбеки)
@dp.message(AdminSendMessage.waiting_for_message_text, F.text)
async def process_message_text(message: Message, state: FSMContext):
    data = await state.get_data()
    target = data.get('target')
    target_name = data.get('target_name')
    text_message = message.text

    await state.clear()

    # Определяем получателей
    if target == "all":
        recipients = SUBSCRIBED_USERS
    elif target == "admins":
        recipients = ADMIN_IDS
    else:
        recipients = [target]

    # Отправляем сообщение
    sent_count = 0
    failed_count = 0

    status_msg = await message.answer(f"📤 Отправляю сообщение {target_name}...")

    for user_id in recipients:
        try:
            await bot.send_message(user_id, f"📨 Сообщение от администратора:\n\n{text_message}")
            sent_count += 1
            await asyncio.sleep(0.1)  # Задержка между отправками
        except Exception as e:
            failed_count += 1
            logging.error(f"Ошибка отправки пользователю {user_id}: {e}")

    await status_msg.edit_text(
        f"📊 Результаты отправки:\n\n"
        f"✅ Успешно: {sent_count}\n"
        f"❌ Не удалось: {failed_count}\n"
        f"👥 Получатель: {target_name}"
    )

    # Логируем
    logging.info(f"Админ {message.from_user.id} отправил сообщение {target_name}: {text_message[:50]}...")

# Помощь для /admin_send
async def send_message_as_admin(target_user_id: int, message_text: str, from_admin_id: int) -> tuple[bool, str]:
    """
    Отправляет сообщение от имени администратора

    Args:
        target_user_id: ID получателя
        message_text: Текст сообщения
        from_admin_id: ID администратора

    Returns:
        (успешно: bool, сообщение_об_ошибке: str)
    """
    try:
        # Проверяем права администратора
        if from_admin_id not in ADMIN_IDS:
            return False, "Недостаточно прав"

        # Проверяем, существует ли пользователь
        if target_user_id not in SUBSCRIBED_USERS:
            # Но всё равно пытаемся отправить
            pass

        # Отправляем сообщение
        await bot.send_message(
            target_user_id,
            f"📨 Сообщение от администратора:\n\n{message_text}"
        )

        # Логируем
        logging.info(f"Админ {from_admin_id} -> Пользователь {target_user_id}: {message_text[:100]}")

        return True, "Сообщение отправлено"

    except Exception as e:
        error_msg = str(e)
        if "user is deactivated" in error_msg.lower():
            return False, "Пользователь заблокировал бота"
        elif "chat not found" in error_msg.lower():
            return False, "Чат не найден"
        elif "bot was blocked" in error_msg.lower():
            return False, "Бот заблокирован пользователем"
        else:
            return False, f"Ошибка: {error_msg}"


# ============ ХЕНДЛЕРЫ БОТА ============

# Получение темы от пользователя - ТОЛЬКО для текстовых сообщений
@dp.message(VideoProcessing.waiting_for_theme, F.text)
async def process_theme(message: Message, state: FSMContext):
    # Проверяем, что есть текст
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текстовое сообщение с темой.")
        return

    theme = message.text.strip()

    if len(theme) < 2:
        await message.answer("❌ Тема слишком короткая. Пожалуйста, введите тему подробнее.")
        return

    if len(theme) > 500:
        await message.answer("❌ Тема слишком длинная. Пожалуйста, уложитесь в 500 символов.")
        return

    await state.update_data(theme=theme)

    await message.answer(
        f"✅ Отлично! Тема сохранена: '{theme}'\n\n"
        f"Теперь отправь мне видео для обработки! 🎬\n\n"
        f"📌 Можно отправить видео файлом или как видеосообщение\n"
        f"⏳ Обработка займет несколько минут"
    )

    await state.set_state(VideoProcessing.waiting_for_video)


# Обработка видео с сохраненной темой
@dp.message(VideoProcessing.waiting_for_video, F.video)
async def handle_video_with_theme(message: Message, state: FSMContext):
    # Получаем сохраненную тему
    user_data = await state.get_data()
    theme = user_data.get('theme', "Философия барберинга, мужской стиль и уход за собой")

    # Уведомляем пользователя
    status_message = await message.answer(f"🎬 Видео получено. Тема: '{theme}'\nНачинаю обработку...")

    await state.set_state(VideoProcessing.processing)

    try:
        # Создаем рабочие папки
        os.makedirs(VIDEOS_FOLDER, exist_ok=True)
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        # Получаем информацию о файле
        video = message.video
        file_info = await bot.get_file(video.file_id)

        # Генерируем уникальные имена файлов
        user_id = message.from_user.id
        timestamp = int(asyncio.get_event_loop().time())
        input_filename = f"temp_{user_id}_{timestamp}.mp4"
        output_filename = f"processed_{user_id}_{timestamp}.mp4"

        input_path = os.path.join(VIDEOS_FOLDER, input_filename)
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        logging.info(f"Скачиваю видео в: {input_path}")
        logging.info(f"Тема: {theme}")

        # Скачиваем видео
        await status_message.edit_text("📥 Скачиваю видео...")
        try:
            await bot.download_file(file_info.file_path, input_path)
            if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                raise Exception("Файл не скачался или пустой")
            logging.info(f"Файл скачан. Размер: {os.path.getsize(input_path)} байт")
        except Exception as e:
            await status_message.edit_text(f"❌ Ошибка скачивания: {str(e)}")
            await state.clear()
            return

        # Обрабатываем видео
        await status_message.edit_text(f"⚙️ Обрабатываю видео...\n🤔 Генерирую текст на тему: '{theme}'")

        # Используем asyncio.to_thread для блокирующих операций
        success, result_msg, title, desc, used_theme = await asyncio.to_thread(
            process_single_video,
            input_path,
            output_path,
            theme
        )

        if not success:
            await status_message.edit_text(f"❌ {result_msg}")
            await state.clear()
            return

        # Проверяем результат
        if not os.path.exists(output_path):
            await status_message.edit_text("❌ Обработанное видео не создано")
            await state.clear()
            return

        # Отправляем результат
        await status_message.edit_text("📤 Отправляю результат...")

        try:
            # Проверяем длину заголовка для Telegram caption
            if title and len(title) > 1024:  # Ограничение Telegram для caption
                caption = f"🎬 {title[:1021]}...\n\n📌 Тема: {used_theme}"
            else:
                caption = f"🎬 {title}\n\n📌 Тема: {used_theme}"

            # Отправляем видео с заголовком как подпись
            video_file = FSInputFile(output_path, filename=output_filename)
            await message.answer_video(
                video_file,
                caption=caption
            )

            # Отправляем описание отдельным сообщением
            if desc and desc != "Описание не сгенерировано":
                # Форматируем описание для лучшей читаемости
                description_text = f"""
📝 ОПИСАНИЕ ДЛЯ INSTAGRAM:
```Копировать
{desc}
```
✨ Текст на видео: "{title}"
🎯 Тема: {used_theme}
                """

                # Разбиваем на части если слишком длинное (ограничение Telegram)
                if len(description_text) > 4096:
                    parts = [description_text[i:i + 4000] for i in range(0, len(description_text), 4000)]
                    for part in parts:
                        await message.answer(part)
                else:
                    await message.answer(description_text, parse_mode='Markdown')

            await status_message.delete()

            # Предлагаем обработать еще одно видео
            await message.answer(
                "✅ Готово! Видео обработано успешно.\n\n"
                "Хочешь обработать еще одно видео?\n"
                "1. Отправь новую тему для текста\n"
                "2. Или просто отправь следующее видео - будет использована стандартная тема\n\n"
                "Для отмены используй /cancel"
            )

            # Возвращаемся в состояние ожидания темы
            await state.set_state(VideoProcessing.waiting_for_theme)

        except Exception as e:
            await status_message.edit_text(f"❌ Ошибка отправки: {str(e)}")
            logging.error(f"Ошибка отправки: {e}")
            await state.clear()

    except Exception as e:
        logging.error(f"Ошибка в handle_video: {e}")
        try:
            await message.answer(f"❌ Произошла ошибка: {str(e)}")
        except:
            pass
        await state.clear()

    finally:
        # Очистка временных файлов
        try:
            if 'input_path' in locals() and os.path.exists(input_path):
                os.remove(input_path)
            if 'output_path' in locals() and os.path.exists(output_path):
                os.remove(output_path)
        except Exception as e:
            logging.error(f"Ошибка при очистке файлов: {e}")


# Обработка видео БЕЗ предварительного выбора темы (используется стандартная тема)
@dp.message(F.video)
async def handle_video_without_theme(message: Message, state: FSMContext):
    current_state = await state.get_state()

    # Если мы в состоянии waiting_for_video, то пропускаем этот хендлер
    # (далее сработает handle_video_with_theme)
    if current_state == VideoProcessing.waiting_for_video:
        return

    # Используем стандартную тему
    standard_theme = "Философия барберинга, мужской стиль и уход за собой"

    await message.answer(
        f"🎬 Видео получено. Использую стандартную тему: '{standard_theme}'\n\n"
        f"⏳ Начинаю обработку...\n\n"
        f"ℹ️ Если хотите задать свою тему, сначала отправьте текст темы, а затем видео"
    )

    # Устанавливаем состояние обработки
    await state.set_state(VideoProcessing.processing)

    try:
        # Создаем рабочие папки
        os.makedirs(VIDEOS_FOLDER, exist_ok=True)
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        # Получаем информацию о файле
        video = message.video
        file_info = await bot.get_file(video.file_id)

        # Генерируем уникальные имена файлов
        user_id = message.from_user.id
        timestamp = int(asyncio.get_event_loop().time())
        input_filename = f"temp_{user_id}_{timestamp}.mp4"
        output_filename = f"processed_{user_id}_{timestamp}.mp4"

        input_path = os.path.join(VIDEOS_FOLDER, input_filename)
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        logging.info(f"Скачиваю видео в: {input_path}")
        logging.info(f"Использую стандартную тему: {standard_theme}")

        # Скачиваем видео
        status_message = await message.answer("📥 Скачиваю видео...")
        try:
            await bot.download_file(file_info.file_path, input_path)
            if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                raise Exception("Файл не скачался или пустой")
            logging.info(f"Файл скачан. Размер: {os.path.getsize(input_path)} байт")
        except Exception as e:
            await status_message.edit_text(f"❌ Ошибка скачивания: {str(e)}")
            await state.clear()
            return

        # Обрабатываем видео
        await status_message.edit_text(f"⚙️ Обрабатываю видео...\n🤔 Генерирую текст на стандартную тему...")

        # Используем asyncio.to_thread для блокирующих операций
        success, result_msg, title, desc, used_theme = await asyncio.to_thread(
            process_single_video,
            input_path,
            output_path,
            standard_theme
        )

        if not success:
            await status_message.edit_text(f"❌ {result_msg}")
            await state.clear()
            return

        # Проверяем результат
        if not os.path.exists(output_path):
            await status_message.edit_text("❌ Обработанное видео не создано")
            await state.clear()
            return

        # Отправляем результат
        await status_message.edit_text("📤 Отправляю результат...")

        try:
            # Проверяем длину заголовка для Telegram caption
            if title and len(title) > 1024:  # Ограничение Telegram для caption
                caption = f"🎬 {title[:1021]}...\n\n📌 Тема: {used_theme}"
            else:
                caption = f"🎬 {title}\n\n📌 Тема: {used_theme}"

            # Отправляем видео с заголовком как подпись
            video_file = FSInputFile(output_path, filename=output_filename)
            await message.answer_video(
                video_file,
                caption=caption
            )

            # Отправляем описание отдельным сообщением
            if desc and desc != "Описание не сгенерировано":
                # Форматируем описание для лучшей читаемости
                description_text = f"""
📝 ОПИСАНИЕ ДЛЯ INSTAGRAM:
```Копировать
{desc}
```
✨ Текст на видео: "{title}"
🎯 Тема: {used_theme}
                """

                # Разбиваем на части если слишком длинное (ограничение Telegram)
                if len(description_text) > 4096:
                    parts = [description_text[i:i + 4000] for i in range(0, len(description_text), 4000)]
                    for part in parts:
                        await message.answer(part)
                else:
                    await message.answer(description_text, parse_mode='Markdown')

            await status_message.delete()

            # Предлагаем обработать еще одно видео
            await message.answer(
                "✅ Готово! Видео обработано успешно.\n\n"
                "Хочешь обработать еще одно видео?\n"
                "1. Отправь новую тему для текста\n"
                "2. Или просто отправь следующее видео - будет использована стандартная тема\n\n"
                "Для отмены используй /cancel"
            )

            # Возвращаемся в состояние ожидания темы
            await state.set_state(VideoProcessing.waiting_for_theme)

        except Exception as e:
            await status_message.edit_text(f"❌ Ошибка отправки: {str(e)}")
            logging.error(f"Ошибка отправки: {e}")
            await state.clear()

    except Exception as e:
        logging.error(f"Ошибка в handle_video_without_theme: {e}")
        try:
            await message.answer(f"❌ Произошла ошибка: {str(e)}")
        except:
            pass
        await state.clear()

    finally:
        # Очистка временных файлов
        try:
            if 'input_path' in locals() and os.path.exists(input_path):
                os.remove(input_path)
            if 'output_path' in locals() and os.path.exists(output_path):
                os.remove(output_path)
        except Exception as e:
            logging.error(f"Ошибка при очистке файлов: {e}")


# Если в состоянии waiting_for_theme пришло фото
@dp.message(VideoProcessing.waiting_for_theme, F.photo)
async def handle_photo_in_theme_state(message: Message):
    await message.answer(
        "📌 Вы отправили фото, но я ожидаю тему для текста.\n\n"
        "Пожалуйста, отправьте текстовое сообщение с темой (например: 'стиль, уход, профессия')\n"
        "Или используйте /default для стандартной темы"
    )


# Если в состоянии waiting_for_theme пришел документ
@dp.message(VideoProcessing.waiting_for_theme, F.document)
async def handle_document_in_theme_state(message: Message):
    await message.answer(
        "📌 Вы отправили документ, но я ожидаю тему для текста.\n\n"
        "Пожалуйста, отправьте текстовое сообщение с темой (например: 'стиль, уход, профессия')\n"
        "Или используйте /default для стандартной темы"
    )


# Обработка текстовых сообщений в неправильном состоянии
@dp.message(VideoProcessing.processing)
async def handle_text_while_processing(message: Message):
    await message.answer("⏳ Пожалуйста, подождите, текущее видео еще обрабатывается...")


# Обработка обычных текстовых сообщений (без состояния или в других состояниях)
@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    current_state = await state.get_state()

    if current_state is None:
        # Если нет активного состояния, предлагаем начать
        await message.answer("Начните с команды /start")
        await state.set_state(VideoProcessing.waiting_for_theme)
    elif current_state == VideoProcessing.waiting_for_video:
        # Если ожидаем видео, но получили текст
        await message.answer(
            "📌 Я ожидаю видео для обработки.\n\n"
            "Пожалуйста, отправьте видео файлом.\n"
            "Если хотите изменить тему, отправьте команду /start\n"
            "Или используйте /default для стандартной темы"
        )
    elif current_state == VideoProcessing.processing:
        # Уже обрабатывается в отдельном хендлере, но на всякий случай
        await message.answer("⏳ Пожалуйста, подождите, текущее видео еще обрабатывается...")
    else:
        # В других случаях (например, в waiting_for_theme), на будущее, если будеи расширяться
        # Этот случай уже обрабатывается хендлером process_theme (waiting_for_theme)
        pass

# ============ GRACEFUL SHUTDOWN ============

async def graceful_shutdown():
    """Плавное завершение работы бота"""
    logging.info("Начинаю плавное завершение работы...")

    try:
        # Отправляем уведомление об остановке только если бот работал
        try:
            text = "🛑 Бот завершает работу. Все текущие операции будут прерваны.\n\nСпасибо за использование!"
            sent, failed = await broadcast_message(text)
            logging.info(f"Уведомление о завершении отправлено: {sent} успешно, {failed} неудачно")
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления о завершении: {e}")
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
    global SUBSCRIBED_USERS

    logging.info("Запуск бота...")

    # Загружаем подписчиков
    SUBSCRIBED_USERS = load_subscribed_users()
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
