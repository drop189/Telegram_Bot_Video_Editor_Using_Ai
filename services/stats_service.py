import io
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, List

import pytz
from matplotlib import pyplot as plt

from settings.config import STATS_FILE

# Константы
STATS_HISTORY_DAYS = 30
moscow_tz = pytz.timezone('Europe/Moscow')


class UsageStats:
    """Класс для управления статистикой использования"""

    def __init__(self, stats_file: str = STATS_FILE):
        self.stats_file = stats_file
        self.stats = self._initialize_stats()
        self.moscow_tz = pytz.timezone('Europe/Moscow')

    def _initialize_stats(self) -> Dict[str, Any]:
        """Инициализирует или загружает статистику"""
        if os.path.exists(self.stats_file):
            try:
                return self._load_and_convert_stats()
            except Exception as e:
                logging.error(f"Ошибка загрузки статистики, создаю новую: {e}")
                return self._create_default_stats()
        else:
            return self._create_default_stats()

    def _create_default_stats(self) -> Dict[str, Any]:
        """Создает статистику по умолчанию с defaultdict"""
        return {
            'videos_processed': 0,
            'videos_failed': 0,
            'total_errors': 0,
            'daily_errors': defaultdict(int),
            'daily_usage': defaultdict(int),
            'user_activity': defaultdict(int),
            'user_errors': defaultdict(int),
            'last_activity': None,
            'last_users': [],
            'peak_hours': defaultdict(int),
            'content_lengths': [],
            'processing_times': [],
            'themes_used': defaultdict(int),
            'start_time': datetime.now(pytz.UTC).isoformat(),
            'uptime_days': 0,
            'sessions': 0,
            'error_types': defaultdict(int)
        }

    def _load_and_convert_stats(self) -> Dict[str, Any]:
        """Загружает статистику и конвертирует словари в defaultdict"""
        with open(self.stats_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Список ключей, которые должны быть defaultdict(int)
        defaultdict_keys = [
            'daily_errors', 'daily_usage', 'user_activity',
            'user_errors', 'peak_hours', 'themes_used', 'error_types'
        ]

        # Конвертируем обычные dict в defaultdict
        for key in defaultdict_keys:
            if key in data and isinstance(data[key], dict):
                data[key] = defaultdict(int, data[key])
            elif key not in data:
                data[key] = defaultdict(int)

        # Убедимся, что все ключи существуют
        default_stats = self._create_default_stats()
        for key, default_value in default_stats.items():
            if key not in data:
                data[key] = default_value

        return data

    def _convert_for_saving(self) -> Dict[str, Any]:
        """Конвертирует статистику для сохранения в JSON"""
        data_to_save = {}

        for key, value in self.stats.items():
            if isinstance(value, defaultdict):
                # Конвертируем defaultdict в обычный dict
                data_to_save[key] = dict(value)
            elif isinstance(value, datetime):
                # Конвертируем datetime в строку
                data_to_save[key] = value.isoformat()
            elif hasattr(value, '__dict__'):
                # Пропускаем объекты
                continue
            else:
                data_to_save[key] = value

        return data_to_save

    def save(self):
        """Сохраняет статистику в файл"""
        try:
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)

            data_to_save = self._convert_for_saving()

            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logging.error(f"Ошибка сохранения статистики: {e}")

    def record_session_start(self):
        """Записывает начало сессии"""
        try:
            self.stats['sessions'] = self.stats.get('sessions', 0) + 1
            self.save()
        except Exception as e:
            logging.error(f"Ошибка записи сессии: {e}")


    def record_video_processed(self, user_id: int, processing_time: float,
                               theme: str = None, content_length: int = None):
        """Записывает успешную обработку видео"""
        try:
            # Получаем текущее время
            current_time = datetime.now(self.moscow_tz)
            today = current_time.strftime('%Y-%m-%d')
            hour = current_time.strftime('%H')  # '01', '02', ..., '23'

            # peak_hours - это defaultdict
            if not isinstance(self.stats['peak_hours'], defaultdict):
                logging.warning("peak_hours не является defaultdict, конвертирую...")
                self.stats['peak_hours'] = defaultdict(int, self.stats['peak_hours'])

            # Безопасное увеличение счетчиков
            self.stats['videos_processed'] += 1
            self.stats['daily_usage'][today] += 1
            self.stats['user_activity'][str(user_id)] += 1
            self.stats['peak_hours'][hour] += 1
            self.stats['last_activity'] = current_time.isoformat()

            # Обновляем список последних пользователей
            user_id_str = str(user_id)
            if user_id_str in self.stats['last_users']:
                self.stats['last_users'].remove(user_id_str)
            self.stats['last_users'].insert(0, user_id_str)
            self.stats['last_users'] = self.stats['last_users'][:10]

            # Записываем тему если есть
            if theme:
                if not isinstance(self.stats['themes_used'], defaultdict):
                    self.stats['themes_used'] = defaultdict(int, self.stats['themes_used'])
                self.stats['themes_used'][theme] += 1

            # Записываем время обработки
            if processing_time > 0:
                self.stats['processing_times'].append(processing_time)
                if len(self.stats['processing_times']) > 100:
                    self.stats['processing_times'].pop(0)

            # Записываем длину контента
            if content_length:
                self.stats['content_lengths'].append(content_length)
                if len(self.stats['content_lengths']) > 100:
                    self.stats['content_lengths'].pop(0)

            # Сохраняем
            self.save()

        except Exception as e:
            logging.error(f"Ошибка в record_video_processed: {e}", exc_info=True)
            # Пытаемся спасти ситуацию
            self._emergency_save()

    def record_error(self, user_id: int, error_type: str = None,
                     error_message: str = None):
        """Записывает ошибку"""
        try:
            today = datetime.now(self.moscow_tz).strftime('%Y-%m-%d')

            # Убедимся, что словари - defaultdict
            if not isinstance(self.stats['daily_errors'], defaultdict):
                self.stats['daily_errors'] = defaultdict(int, self.stats['daily_errors'])

            if not isinstance(self.stats['user_errors'], defaultdict):
                self.stats['user_errors'] = defaultdict(int, self.stats['user_errors'])

            if 'error_types' not in self.stats or not isinstance(self.stats['error_types'], defaultdict):
                self.stats['error_types'] = defaultdict(int)

            # Увеличиваем счетчики
            self.stats['total_errors'] += 1
            self.stats['videos_failed'] += 1
            self.stats['daily_errors'][today] += 1
            self.stats['user_errors'][str(user_id)] += 1

            if error_type:
                self.stats['error_types'][error_type] += 1

            self.save()

        except Exception as e:
            logging.error(f"Ошибка в record_error: {e}")
            self._emergency_save()

    def _emergency_save(self):
        """Аварийное сохранение только основных полей"""
        try:
            emergency_data = {
                'videos_processed': self.stats.get('videos_processed', 0),
                'total_errors': self.stats.get('total_errors', 0),
                'start_time': self.stats.get('start_time', datetime.now(pytz.UTC).isoformat()),
                'last_activity': self.stats.get('last_activity', datetime.now(pytz.UTC).isoformat())
            }

            with open(self.stats_file + '.backup', 'w', encoding='utf-8') as f:
                json.dump(emergency_data, f)

        except Exception as e:
            logging.error(f"Даже аварийное сохранение не удалось: {e}")

    def update_uptime(self):
        """Обновляет время работы"""
        try:
            if 'start_time' not in self.stats:
                self.stats['start_time'] = datetime.now(pytz.UTC).isoformat()

            # Парсим время старта
            start_time_str = self.stats['start_time']
            if start_time_str.endswith('Z'):
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            else:
                # Пробуем разные форматы
                try:
                    start_time = datetime.fromisoformat(start_time_str)
                except ValueError:
                    # Старый формат
                    start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')

            # Приводим к UTC если нужно
            if start_time.tzinfo is None:
                start_time = pytz.UTC.localize(start_time)

            # Текущее время в UTC
            current_time = datetime.now(pytz.UTC)

            # Вычисляем разницу
            delta = current_time - start_time
            self.stats['uptime_days'] = delta.days

            self.save()

        except Exception as e:
            logging.error(f"Ошибка в update_uptime: {e}")
            self.stats['uptime_days'] = 0

    def get_daily_stats(self, days: int = 7) -> Dict:
        """Получает статистику за последние N дней"""
        result = {
            'dates': [],
            'usage': [],
            'errors': []
        }

        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            result['dates'].insert(0, date)
            result['usage'].insert(0, self.stats['daily_usage'].get(date, 0))
            result['errors'].insert(0, self.stats['daily_errors'].get(date, 0))

        return result

    def get_top_users(self, limit: int = 5) -> List[tuple]:
        """Получает топ пользователей по активности"""
        users = [(uid, count) for uid, count in self.stats['user_activity'].items()]
        return sorted(users, key=lambda x: x[1], reverse=True)[:limit]

    def get_top_themes(self, limit: int = 5) -> List[tuple]:
        """Получает самые популярные темы"""
        themes = [(theme, count) for theme, count in self.stats['themes_used'].items()]
        return sorted(themes, key=lambda x: x[1], reverse=True)[:limit]

    def get_average_processing_time(self) -> float:
        """Среднее время обработки"""
        if not self.stats['processing_times']:
            return 0
        return sum(self.stats['processing_times']) / len(self.stats['processing_times'])

    def get_success_rate(self) -> float:
        """Процент успешных обработок"""
        total = self.stats['videos_processed'] + self.stats['videos_failed']
        if total == 0:
            return 100.0
        return (self.stats['videos_processed'] / total) * 100


# Глобальный экземпляр
usage_stats = UsageStats()


async def create_activity_chart(weekly_stats: Dict) -> bytes:
    """Создает график активности"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # График запросов
    dates = weekly_stats['dates']
    ax1.bar(dates, weekly_stats['usage'], color='skyblue', label='Запросы')
    ax1.set_title('📊 Активность за 7 дней', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Количество запросов')
    ax1.tick_params(axis='x', rotation=45)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # График ошибок
    ax2.bar(dates, weekly_stats['errors'], color='salmon', label='Ошибки')
    ax2.set_title('❌ Ошибки за 7 дней', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Количество ошибок')
    ax2.tick_params(axis='x', rotation=45)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    # Сохраняем в буфер
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)

    return buf.getvalue()
