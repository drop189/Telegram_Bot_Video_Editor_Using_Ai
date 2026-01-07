import logging

from aiogram.dispatcher.middlewares.base import BaseMiddleware

logger = logging.getLogger(__name__)


class StateLoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        state = data.get("state")

        if state:
            current_state = await state.get_state()
            user = data.get("event_from_user")

            # Логируем вход в обработчик
            user_info = f"user_{user.id}" if user else "unknown"
            logger.debug(f"Обработчик: {handler.__name__}, "
                         f"Пользователь: {user_info}, "
                         f"Состояние: {current_state}")

            # Вызываем следующий обработчик
            result = await handler(event, data)

            # Логируем новое состояние после обработки
            new_state = await state.get_state()
            if new_state != current_state:
                logger.info(f"Смена состояния: {current_state} → {new_state}, "
                            f"Пользователь: {user_info}")

            return result

        return await handler(event, data)
