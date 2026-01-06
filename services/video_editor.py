import logging
import os
import subprocess
import textwrap
from PIL import Image, ImageDraw, ImageFont
from config import FFMPEG_PATH, FONT_PATH
from services.ai_service import generate_title_and_description


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


# Добавление текста
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


def create_rounded_text_image(text, output_path, video_width, video_height, bg_color, text_color, font_path=None):
    """
    Создает PNG с прозрачным фоном, текстом и закругленной подложкой.
    """

    # Максимальная ширина текста (90% от ширины видео)
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
    if avg_char_width == 0: avg_char_width = 1  # Защита от деления на ноль
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

    # Высота всего изображения
    total_height = sum(item["box_h"] for item in line_infos) + (len(lines) - 1)

    # Создаем итоговое изображение с прозрачностью (RGBA)
    image = Image.new("RGBA", (max_box_width, total_height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    radius = int(font_size / 2)
    current_y = 0

    # Для начала нарисуем все прямоугольники и сразу сохраним их координаты
    rectangles_cords = []

    for i, item in enumerate(line_infos):
        box_w = item["box_w"]
        box_h = item["box_h"]

        # X координата (центрирование)
        x = (max_box_width - box_w) // 2

        # Сохраняем координаты текущего прямоугольника: (x1, y1, x2, y2)
        rect_cords = (x, current_y, x + box_w, current_y + box_h)
        rectangles_cords.append(rect_cords)

        # Рисуем сам прямоугольник
        draw.rounded_rectangle(
            rect_cords,
            radius=radius,
            fill=bg_color
        )

        # Рисуем текст (логика осталась прежней)
        txt = item["text"]
        bbox = item["bbox"]

        # Вычисляем X, чтобы подложка была по центру общей картинки
        x = (max_box_width - box_w) // 2

        box_center_y = current_y + (box_h / 2)
        text_center_y = (bbox[1] + bbox[3]) / 2
        text_offset_y = text_center_y

        # Рисуем текст внутри подложки
        text_x = x + padding_x
        text_y = box_center_y - text_offset_y + (font_size * 0.1)

        draw.text((text_x, text_y), txt, font=font, fill=text_color)

        # Сдвигаем Y
        current_y += box_h

    # Проходим по парам прямоугольников и соединяем их уголки (не понимаю, работает ли)
    for i in range(len(rectangles_cords) - 1):
        r1 = rectangles_cords[i]  # Верхний прямоугольник
        r2 = rectangles_cords[i + 1]  # Нижний прямоугольник

        # Координаты нижних углов верхнего прямоугольника
        r1_x1, r1_y1, r1_x2, r1_y2 = r1
        # Координаты верхних углов нижнего прямоугольника
        r2_x1, r2_y1, r2_x2, r2_y2 = r2

        # Соединяем (r1_x1, r1_y2) с (r2_x1, r2_y1)

        pxw = 50
        if r1_x1 == r2_x1:  # Если выравнивание по левому краю совпадает
            # Рисуем линию шириной pxw px от низа верхнего до верха нижнего
            draw.rectangle([(r1_x1, r1_y2), (r1_x1 + pxw, r2_y1)], fill=bg_color)

        # ПРАВАЯ щель
        if r1_x2 == r2_x2:
            # r1_x2 - pxw, чтобы линия была шириной pxw px внутрь прямоугольника
            draw.rectangle([(r1_x2 - pxw, r1_y2), (r1_x2, r2_y1)], fill=bg_color)

    # Сохраняем
    image.save(output_path)
    return output_path


def add_text_with_rounded_box(input_video, output_video, text, font_path):
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
        if add_text_with_rounded_box(input_path, output_path, text, FONT_PATH):
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
