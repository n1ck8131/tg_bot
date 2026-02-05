"""
Обработчики для обычных пользователей (не админа).
"""

import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.messages import Messages, Emojis
from app.services.yandex_music import yandex_music_service, process_track_submission
from app.services.photo_contest import handle_photo_submission
from app.storage import photo_contest_storage
from app.constants import MAX_PHOTO_CONTEST_PARTICIPANTS, YANDEX_MUSIC_URL_PATTERN

logger = logging.getLogger(__name__)

user_router = Router()

ADMIN_ID = settings.bot.admin_id


# === Start для обычных пользователей ===

@user_router.message(
    CommandStart(),
    F.chat.type == ChatType.PRIVATE,
    ~(F.from_user.id == ADMIN_ID)
)
async def cmd_start_user(message: Message) -> None:
    await message.answer(
        Messages.WELCOME_USER,
        parse_mode="Markdown"
    )


# === Обработка фото для конкурса ===

@user_router.message(
    F.chat.type == ChatType.PRIVATE,
    F.photo,
    ~(F.from_user.id == ADMIN_ID)
)
async def handle_private_photo(message: Message) -> None:
    await handle_photo_submission(message)


# === Обработка ссылок Яндекс.Музыки ===

@user_router.message(
    F.chat.type == ChatType.PRIVATE,
    F.text.regexp(YANDEX_MUSIC_URL_PATTERN),
    ~(F.from_user.id == ADMIN_ID)
)
async def handle_private_yandex_link(message: Message) -> None:
    """Автоматическая обработка ссылок на Яндекс.Музыку."""
    if not yandex_music_service.is_configured:
        await message.answer(f"{Emojis.ERROR} {Messages.PLAYLIST_NOT_CONFIGURED}")
        return

    await process_track_submission(message, is_admin=False)


# === Обработка остальных личных сообщений ===

@user_router.message(
    F.chat.type == ChatType.PRIVATE,
    ~(F.from_user.id == ADMIN_ID)
)
async def handle_private_other(message: Message) -> None:
    await message.answer(
        f"{Emojis.INFO} Отправь фото для конкурса или ссылку на трек Яндекс.Музыки.\n\n"
        f"Для справки используй /start"
    )
