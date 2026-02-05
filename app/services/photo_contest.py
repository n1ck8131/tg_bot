"""Сервис для работы с фото-конкурсом."""

import logging
from typing import TYPE_CHECKING

from app.storage import photo_contest_storage, PhotoEntry
from app.messages import Messages, Emojis
from app.constants import MAX_PHOTO_CONTEST_PARTICIPANTS, MAX_POLL_OPTIONS

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import Message

logger = logging.getLogger(__name__)


async def handle_photo_submission(message: "Message") -> None:
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


async def send_contest_photos(bot: "Bot", group_id: int, entries: list) -> None:
    """Отправляет все фото конкурса в группу."""
    for i, (user_id, entry) in enumerate(entries, 1):
        await bot.send_photo(
            group_id,
            photo=entry.photo_id,
            caption=f"{Emojis.CAMERA} {Messages.PHOTO_CAPTION.format(num=i, user=entry.user_name)}"
        )


async def create_contest_polls(bot: "Bot", group_id: int, entries: list) -> None:
    """Создаёт опросы для голосования (макс. участников в опросе из константы MAX_POLL_OPTIONS)."""
    total_entries = len(entries)
    poll_count = (total_entries + MAX_POLL_OPTIONS - 1) // MAX_POLL_OPTIONS  # Округление вверх

    for poll_num in range(poll_count):
        start_idx = poll_num * MAX_POLL_OPTIONS
        end_idx = min(start_idx + MAX_POLL_OPTIONS, total_entries)
        poll_entries = entries[start_idx:end_idx]

        options = [
            Messages.PHOTO_OPTION.format(num=start_idx + i + 1, user=entry.user_name)
            for i, (_, entry) in enumerate(poll_entries)
        ]

        if len(options) >= 2:
            poll_question = f"{Emojis.TROPHY} {Messages.PHOTO_CONTEST_VOTE_QUESTION}"
            if poll_count > 1:
                poll_question += f" (Опрос {poll_num + 1} из {poll_count})"

            await bot.send_poll(
                chat_id=group_id,
                question=poll_question,
                options=options,
                is_anonymous=False
            )


async def stop_photo_contest(message: "Message", bot: "Bot", group_id: int) -> None:
    """Останавливает фото-конкурс и создаёт голосование."""
    photo_contest_storage.stop()

    if photo_contest_storage.is_empty():
        await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_NO_ENTRIES}")
        await bot.send_message(group_id, f"{Emojis.PHOTO} {Messages.PHOTO_CONTEST_ENDED_EMPTY}")
        return

    await bot.send_message(
        group_id,
        f"{Emojis.PHOTO} {Messages.PHOTO_CONTEST_ENDED}",
        parse_mode="Markdown"
    )

    entries = photo_contest_storage.get_entries()

    await send_contest_photos(bot, group_id, entries)
    await create_contest_polls(bot, group_id, entries)

    await message.answer(
        f"{Emojis.SUCCESS} {Messages.PHOTO_CONTEST_VOTING_CREATED.format(count=photo_contest_storage.entries_count())}"
    )
