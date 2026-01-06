import json
import logging
import random
import requests
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL


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
