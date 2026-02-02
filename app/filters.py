"""
Фильтры для обработчиков.
Переиспользуемые фильтры для различных типов чатов и пользователей.
"""

from aiogram import F
from aiogram.enums import ChatType
from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.config import settings


class IsAdminPrivateFilter(BaseFilter):
    """Фильтр для приватных сообщений от администратора."""

    async def __call__(self, message: Message) -> bool:
        return (
            message.chat.type == ChatType.PRIVATE
            and message.from_user is not None
            and message.from_user.id == settings.bot.admin_id
        )


class IsUserPrivateFilter(BaseFilter):
    """Фильтр для приватных сообщений от обычных пользователей (не админ)."""

    async def __call__(self, message: Message) -> bool:
        return (
            message.chat.type == ChatType.PRIVATE
            and message.from_user is not None
            and message.from_user.id != settings.bot.admin_id
        )


class IsGroupChatFilter(BaseFilter):
    """Фильтр для сообщений из группового чата."""

    async def __call__(self, message: Message) -> bool:
        return message.chat.id == settings.bot.group_id


# Удобные константы для использования в декораторах
IS_ADMIN_PRIVATE = (F.chat.type == ChatType.PRIVATE) & (F.from_user.id == settings.bot.admin_id)
IS_USER_PRIVATE = (F.chat.type == ChatType.PRIVATE) & ~(F.from_user.id == settings.bot.admin_id)
IS_GROUP_CHAT = F.chat.id == settings.bot.group_id
