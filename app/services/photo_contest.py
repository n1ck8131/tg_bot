"""Сервис для работы с фото-конкурсом."""

import asyncio
import logging
from typing import TYPE_CHECKING

from aiogram.exceptions import TelegramRetryAfter

from app.storage import photo_contest_storage, PhotoEntry
from app.messages import Messages, Emojis
from app.constants import MAX_PHOTO_CONTEST_PARTICIPANTS, PHOTO_SEND_DELAY, PHOTO_SEND_MAX_RETRIES
from app.keyboards import get_photo_voting_keyboard

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import Message

logger = logging.getLogger(__name__)

MEDALS = {1: "🥇 ", 2: "🥈 ", 3: "🥉 "}


async def handle_photo_submission(
    message: "Message", is_admin: bool = False, silent: bool = False
) -> bool:
    """Обрабатывает отправку фото на конкурс.

    Args:
        message: Сообщение с фото
        is_admin: Если True, админ может отправлять несколько фото
        silent: Если True, не отправлять ответ (для batch-обработки альбомов)

    Returns:
        True если фото принято, False если отклонено
    """
    if not photo_contest_storage.is_active:
        if not silent:
            await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_INACTIVE}")
        return False

    user_id = message.from_user.id

    if not is_admin:
        if photo_contest_storage.has_entry(user_id):
            if not silent:
                await message.answer(f"{Emojis.WARNING} {Messages.PHOTO_ALREADY_SENT}")
            return False

        if photo_contest_storage.entries_count() >= MAX_PHOTO_CONTEST_PARTICIPANTS:
            if not silent:
                await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_MAX_REACHED}")
            return False

    user_name = message.from_user.full_name
    if message.from_user.username:
        user_name = f"@{message.from_user.username}"

    photo_id = message.photo[-1].file_id

    photo_contest_storage.add_entry(
        user_id,
        PhotoEntry(photo_id=photo_id, user_name=user_name, user_id=user_id),
        is_admin=is_admin
    )

    if not silent:
        count_msg = f" (#{photo_contest_storage.entries_count()})" if is_admin else ""
        await message.answer(f"{Emojis.SUCCESS} {Messages.PHOTO_ACCEPTED}{count_msg}")

    logger.info(f"Фото для конкурса от {user_name}" + (" [admin test]" if is_admin else ""))
    return True


async def send_contest_photos(bot: "Bot", group_id: int, entries: list) -> None:
    """Отправляет все фото конкурса в группу с учётом rate limit Telegram."""
    for i, (user_id, entry) in enumerate(entries, 1):
        for attempt in range(1, PHOTO_SEND_MAX_RETRIES + 1):
            try:
                await bot.send_photo(
                    group_id,
                    photo=entry.photo_id,
                    caption=f"{Emojis.CAMERA} {Messages.PHOTO_CAPTION.format(num=i, user=entry.user_name)}"
                )
                break
            except TelegramRetryAfter as e:
                logger.warning(
                    f"Rate limit при отправке фото {i}/{len(entries)}, "
                    f"попытка {attempt}/{PHOTO_SEND_MAX_RETRIES}, "
                    f"ждём {e.retry_after}с"
                )
                await asyncio.sleep(e.retry_after)
        if i < len(entries):
            await asyncio.sleep(PHOTO_SEND_DELAY)


async def stop_photo_submissions(message: "Message", bot: "Bot", group_id: int) -> None:
    """Останавливает приём фото (но НЕ запускает голосование)."""
    photo_contest_storage.stop()

    if photo_contest_storage.is_empty():
        await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_NO_ENTRIES}")
        await bot.send_message(group_id, f"{Emojis.PHOTO} {Messages.PHOTO_CONTEST_ENDED_EMPTY}")
        photo_contest_storage.clear()
        return

    count = photo_contest_storage.entries_count()
    await message.answer(
        f"{Emojis.SUCCESS} {Messages.PHOTO_CONTEST_SUBMISSIONS_CLOSED.format(count=count)}"
    )


async def start_voting(message: "Message", bot: "Bot", group_id: int) -> None:
    """Начинает голосование: отправляет фото в группу и создает кнопки для голосования."""
    if photo_contest_storage.is_empty():
        await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_NO_ENTRIES}")
        return

    photo_contest_storage.start_voting()

    await bot.send_message(
        group_id,
        f"{Emojis.PHOTO} {Messages.PHOTO_CONTEST_ENDED}",
        parse_mode="Markdown"
    )

    entries = photo_contest_storage.get_entries()
    await send_contest_photos(bot, group_id, entries)

    await bot.send_message(
        group_id,
        f"{Emojis.TROPHY} {Messages.PHOTO_VOTING_STARTED}",
        parse_mode="Markdown",
        reply_markup=get_photo_voting_keyboard(entries)
    )

    await message.answer(
        f"{Emojis.SUCCESS} {Messages.PHOTO_VOTING_CREATED.format(count=photo_contest_storage.entries_count())}"
    )
    logger.info(f"Голосование за фото начато. Участников: {len(entries)}")


async def end_voting(message: "Message", bot: "Bot", group_id: int) -> None:
    """Завершает голосование и объявляет результаты."""
    photo_contest_storage.stop_voting()

    if photo_contest_storage.is_empty():
        await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_NO_ENTRIES}")
        return

    vote_counts = photo_contest_storage.get_vote_counts()
    entries = photo_contest_storage.get_entries()

    # Собрать все записи с количеством голосов
    all_results: list[tuple[int, str, int, int]] = []  # (entry_key, user_name, user_id, votes)
    for entry_key, entry in entries:
        votes = vote_counts.get(entry_key, 0)
        all_results.append((entry_key, entry.user_name, entry.user_id, votes))

    # Сортировка по голосам (убывание)
    all_results.sort(key=lambda x: x[3], reverse=True)

    # Определение мест с учётом одинаковых голосов
    results_text = ""
    winners: list[tuple[str, int]] = []  # (user_name, user_id) для 1 места
    current_place = 1

    for i, (entry_key, user_name, user_id, votes) in enumerate(all_results):
        # Если не первый элемент и голосов меньше, чем у предыдущего — пересчитать место
        if i > 0 and votes < all_results[i - 1][3]:
            current_place = i + 1

        medal = MEDALS.get(current_place, "")
        vote_word = _get_vote_word(votes)
        results_text += f"{medal}{current_place} место — {user_name}: {votes} {vote_word}\n"

        if current_place == 1:
            winners.append((user_name, user_id))

    # Текст поздравления
    if len(winners) == 1:
        winner_text = Messages.PHOTO_WINNER_SINGLE
    else:
        winner_text = Messages.PHOTO_WINNER_MULTIPLE

    # Ссылки на профили победителей
    winner_links = ", ".join(
        f"[{name}](tg://user?id={uid})" for name, uid in winners
    )

    await bot.send_message(
        group_id,
        Messages.PHOTO_VOTING_RESULTS.format(
            results=results_text,
            winner_text=winner_text,
            winner_links=winner_links,
        ),
        parse_mode="Markdown"
    )

    await message.answer(f"{Emojis.SUCCESS} Результаты голосования опубликованы!")
    logger.info(f"Голосование завершено. Всего голосов: {sum(vote_counts.values())}")

    photo_contest_storage.clear()


def _get_vote_word(count: int) -> str:
    """Возвращает правильное склонение слова 'голос'."""
    if count % 10 == 1 and count % 100 != 11:
        return "голос"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return "голоса"
    else:
        return "голосов"
