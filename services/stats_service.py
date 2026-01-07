import io
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from matplotlib import pyplot as plt

from settings.config import STATS_FILE

# Константы
STATS_HISTORY_DAYS = 30


class UsageStats:
    """Класс для управления статистикой использования"""

    def __init__(self, stats_file: str = STATS_FILE):
        self.stats_file = stats_file
        self.stats = self._load_stats()

    def _load_stats(self) -> Dict:
        """Загружает статистику из файла"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Ошибка загрузки статистики: {e}")

        # Базовая структура по умолчанию
        return {
            'videos_processed': 0,
            'videos_failed': 0,
            'total_errors': 0,
            'daily_errors': defaultdict(int),
            'daily_usage': defaultdict(int),
            'user_activity': defaultdict(int),  # user_id: count
            'user_errors': defaultdict(int),  # user_id: error_count
            'last_activity': None,
            'last_users': [],  # последние 10 активных пользователей
            'peak_hours': defaultdict(int),  # час: количество запросов
            'content_lengths': [],  # длины сгенерированных текстов
            'processing_times': [],  # время обработки видео
            'themes_used': defaultdict(int),  # тема: количество использований
            'start_time': datetime.now().isoformat(),
            'uptime_days': 0,
            'sessions': 0
        }

    def _save_stats(self):
        """Сохраняет статистику в файл"""
        try:
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)

            # Конвертируем defaultdict в обычные dict для JSON
            stats_to_save = {}
            for key, value in self.stats.items():
                if isinstance(value, defaultdict):
                    stats_to_save[key] = dict(value)
                else:
                    stats_to_save[key] = value

            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_to_save, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logging.error(f"Ошибка сохранения статистики: {e}")

    def update_uptime(self):
        """Обновляет время работы"""
        start_time = datetime.fromisoformat(self.stats['start_time'])
        self.stats['uptime_days'] = (datetime.now() - start_time).days

    def record_video_processed(self, user_id: int, processing_time: float,
                               theme: str = None, content_length: int = None):
        """Записывает успешную обработку видео"""
        today = datetime.now().strftime('%Y-%m-%d')
        hour = datetime.now().strftime('%H')

        self.stats['videos_processed'] += 1
        self.stats['daily_usage'][today] += 1
        self.stats['user_activity'][str(user_id)] += 1
        self.stats['peak_hours'][hour] += 1
        self.stats['last_activity'] = datetime.now().isoformat()

        # Обновляем список последних пользователей
        if str(user_id) not in self.stats['last_users']:
            self.stats['last_users'].insert(0, str(user_id))
            self.stats['last_users'] = self.stats['last_users'][:10]  # держим только 10

        if theme:
            self.stats['themes_used'][theme] += 1

        if processing_time:
            self.stats['processing_times'].append(processing_time)
            # Держим только последние 100 записей
            if len(self.stats['processing_times']) > 100:
                self.stats['processing_times'].pop(0)

        if content_length:
            self.stats['content_lengths'].append(content_length)
            if len(self.stats['content_lengths']) > 100:
                self.stats['content_lengths'].pop(0)

        self._save_stats()

    def record_error(self, user_id: int, error_type: str = None):
        """Записывает ошибку"""
        today = datetime.now().strftime('%Y-%m-%d')

        self.stats['total_errors'] += 1
        self.stats['videos_failed'] += 1
        self.stats['daily_errors'][today] += 1
        self.stats['user_errors'][str(user_id)] = self.stats['user_errors'].get(str(user_id), 0) + 1

        if error_type:
            if 'error_types' not in self.stats:
                self.stats['error_types'] = defaultdict(int)
            self.stats['error_types'][error_type] += 1

        self._save_stats()

    def record_session_start(self):
        """Записывает начало сессии"""
        self.stats['sessions'] += 1

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
