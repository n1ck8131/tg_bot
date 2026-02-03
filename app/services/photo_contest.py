"""Сервис для работы с фото-конкурсом."""

import logging
from aiogram.types import Message
from app.storage import photo_contest_storage, PhotoEntry
from app.messages import Messages, Emojis
from app.constants import MAX_PHOTO_CONTEST_PARTICIPANTS

logger = logging.getLogger(__name__)


async def handle_photo_submission(message: Message) -> None:
    """Обрабатывает отправку фото на конкурс."""
    if not photo_contest_storage.is_active:
        await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_INACTIVE}")
        return

    user_id = message.from_user.id

    if photo_contest_storage.has_entry(user_id):
        await message.answer(f"{Emojis.WARNING} {Messages.PHOTO_ALREADY_SENT}")
        return

    if photo_contest_storage.entries_count() >= MAX_PHOTO_CONTEST_PARTICIPANTS:
        await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_MAX_REACHED}")
        return

    user_name = message.from_user.full_name
    if message.from_user.username:
        user_name = f"@{message.from_user.username}"

    photo_id = message.photo[-1].file_id

    photo_contest_storage.add_entry(
        user_id,
        PhotoEntry(photo_id=photo_id, user_name=user_name)
    )

    await message.answer(f"{Emojis.SUCCESS} {Messages.PHOTO_ACCEPTED}")
    logger.info(f"Фото для конкурса от {user_name}")
