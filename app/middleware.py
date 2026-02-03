"""
Middleware для обработки запросов.
"""

import logging
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов (rate limiting).
    Защищает от спама и DoS атак.
    """

    def __init__(
        self,
        rate_limit: int = 5,  # Максимум сообщений
        time_window: int = 10,  # За период времени в секундах
    ):
        """
        Args:
            rate_limit: Максимальное количество сообщений от пользователя
            time_window: Временное окно в секундах
        """
        self.rate_limit = rate_limit
        self.time_window = time_window
        # Словарь: user_id -> список timestamps
        self.user_requests: Dict[int, list[float]] = {}
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Получаем user_id из события
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        # Пропускаем события без user_id или от админа
        if not user_id or user_id == settings.bot.admin_id:
            return await handler(event, data)

        current_time = time.time()

        # Инициализируем список запросов для нового пользователя
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []

        # Удаляем старые запросы за пределами временного окна
        self.user_requests[user_id] = [
            req_time
            for req_time in self.user_requests[user_id]
            if current_time - req_time < self.time_window
        ]

        # Удаляем пользователей без активных запросов
        if not self.user_requests[user_id]:
            del self.user_requests[user_id]
            return await handler(event, data)

        # Проверяем лимит
        if len(self.user_requests[user_id]) >= self.rate_limit:
            logger.warning(
                f"Rate limit exceeded for user {user_id}: "
                f"{len(self.user_requests[user_id])} requests in {self.time_window}s"
            )

            # Отправляем предупреждение только если это сообщение
            if isinstance(event, Message):
                try:
                    await event.answer(
                        "⚠️ Слишком много запросов. Подождите немного и попробуйте снова."
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить rate limit предупреждение: {e}")

            # Не обрабатываем запрос
            return None

        # Добавляем текущий запрос
        self.user_requests[user_id].append(current_time)

        # Продолжаем обработку
        return await handler(event, data)
