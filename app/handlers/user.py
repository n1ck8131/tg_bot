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
from app.callbacks import UserCallbacks
from app.keyboards import get_user_reply_keyboard
from app.states import AddTrackState
from app.storage import photo_contest_storage, PhotoEntry
from app.services.yandex_music import yandex_music_service

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
    show_photo = photo_contest_storage.is_active
    await message.answer(
        f"{Emojis.WAVE} {Messages.WELCOME_USER_CONTEST if show_photo else Messages.WELCOME_USER_NO_CONTEST}",
        parse_mode="Markdown",
        reply_markup=get_user_reply_keyboard(show_photo=show_photo)
    )


# === Reply-кнопка "Отправить фото" ===

@user_router.message(
    F.text == f"{Emojis.PHOTO} Отправить фото",
    F.chat.type == ChatType.PRIVATE,
    ~(F.from_user.id == ADMIN_ID)
)
async def user_reply_send_photo(message: Message) -> None:
    if photo_contest_storage.is_active:
        user_id = message.from_user.id
        if photo_contest_storage.has_entry(user_id):
            await message.answer(f"{Emojis.WARNING} {Messages.PHOTO_ALREADY_SENT}")
        else:
            await message.answer(f"{Emojis.PHOTO} {Messages.PHOTO_SEND_PROMPT}")
    else:
        await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_INACTIVE}")


# === Reply-кнопка "Добавить трек" ===

@user_router.message(
    F.text == f"{Emojis.MUSIC} Добавить трек",
    F.chat.type == ChatType.PRIVATE,
    ~(F.from_user.id == ADMIN_ID)
)
async def user_reply_add_track(message: Message, state: FSMContext) -> None:
    if not yandex_music_service.is_configured:
        await message.answer(f"{Emojis.ERROR} {Messages.PLAYLIST_NOT_CONFIGURED}")
        return

    await state.set_state(AddTrackState.waiting_for_link)
    await message.answer(
        f"{Emojis.MUSIC} {Messages.PLAYLIST_INFO_PRIVATE}",
        parse_mode="Markdown"
    )


# === Callback "Отправить фото" ===

@user_router.callback_query(
    F.data == UserCallbacks.SEND_PHOTO,
    ~(F.from_user.id == ADMIN_ID)
)
async def user_callback_send_photo(callback: CallbackQuery) -> None:
    if photo_contest_storage.is_active:
        user_id = callback.from_user.id
        if photo_contest_storage.has_entry(user_id):
            await callback.message.answer(f"{Emojis.WARNING} {Messages.PHOTO_ALREADY_SENT}")
        else:
            await callback.message.answer(f"{Emojis.PHOTO} {Messages.PHOTO_SEND_PROMPT}")
    else:
        await callback.message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_INACTIVE}")
    await callback.answer()


@user_router.callback_query(
    F.data == UserCallbacks.NO_CONTEST,
    ~(F.from_user.id == ADMIN_ID)
)
async def user_callback_no_contest(callback: CallbackQuery) -> None:
    await callback.message.answer(f"{Emojis.INFO} {Messages.PHOTO_CONTEST_WAIT}")
    await callback.answer()


# === Callback "Добавить трек" ===

@user_router.callback_query(
    F.data == UserCallbacks.ADD_TRACK,
    ~(F.from_user.id == ADMIN_ID)
)
async def user_callback_add_track(callback: CallbackQuery, state: FSMContext) -> None:
    if not yandex_music_service.is_configured:
        await callback.message.answer(f"{Emojis.ERROR} {Messages.PLAYLIST_NOT_CONFIGURED}")
        await callback.answer()
        return

    await state.set_state(AddTrackState.waiting_for_link)
    await callback.message.answer(
        f"{Emojis.MUSIC} {Messages.PLAYLIST_INFO_PRIVATE}",
        parse_mode="Markdown"
    )
    await callback.answer()


# === Обработка ссылки на трек ===

@user_router.message(
    AddTrackState.waiting_for_link,
    F.chat.type == ChatType.PRIVATE,
    ~(F.from_user.id == ADMIN_ID)
)
async def process_track_link(message: Message, state: FSMContext) -> None:
    text = message.text or ""

    track_id = yandex_music_service.extract_track_id(text)
    if not track_id:
        await message.answer(f"{Emojis.ERROR} {Messages.TRACK_INVALID_LINK}")
        return

    await state.clear()
    await _add_track_to_playlist(message, track_id)


async def _add_track_to_playlist(message: Message, track_id: str) -> None:
    """Добавляет трек в плейлист."""
    success, error, track_info = await yandex_music_service.add_track_to_playlist(track_id)

    if success and track_info:
        user = message.from_user
        user_name = f"@{user.username}" if user.username else user.full_name
        track_title = f"{track_info.artists} — {track_info.title}"

        # Уведомляем пользователя
        await message.answer(
            f"{Emojis.SUCCESS} {Messages.TRACK_ADDED.format(title=track_title, user=user_name)}",
            parse_mode="Markdown"
        )

        logger.info(f"Трек {track_id} добавлен пользователем {user_name}")
    else:
        error_messages = {
            "connection_error": Messages.TRACK_CONNECTION_ERROR,
            "track_not_found": Messages.TRACK_NOT_FOUND,
            "playlist_not_found": Messages.PLAYLIST_ID_NOT_SET,
            "rate_limit": Messages.TRACK_RATE_LIMIT,
            "network_error": Messages.TRACK_NETWORK_ERROR,
        }
        error_msg = error_messages.get(error, Messages.TRACK_ERROR.format(error=error))
        await message.answer(f"{Emojis.ERROR} {error_msg}")


# === Автоматическое распознавание ссылок на Яндекс Музыку ===

@user_router.message(
    F.chat.type == ChatType.PRIVATE,
    F.text.regexp(r'music\.yandex\.(ru|com)/album/\d+/track/\d+'),
    ~(F.from_user.id == ADMIN_ID)
)
async def handle_yandex_music_link(message: Message) -> None:
    """Автоматическое добавление трека при отправке ссылки."""
    if not yandex_music_service.is_configured:
        await message.answer(f"{Emojis.ERROR} {Messages.PLAYLIST_NOT_CONFIGURED}")
        return

    track_id = yandex_music_service.extract_track_id(message.text)
    if track_id:
        await _add_track_to_playlist(message, track_id)


# === Обработка фото для конкурса ===

@user_router.message(
    F.chat.type == ChatType.PRIVATE,
    F.photo,
    ~(F.from_user.id == ADMIN_ID)
)
async def handle_private_photo(message: Message) -> None:
    if not photo_contest_storage.is_active:
        await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_INACTIVE}")
        return

    user_id = message.from_user.id

    if photo_contest_storage.has_entry(user_id):
        await message.answer(f"{Emojis.WARNING} {Messages.PHOTO_ALREADY_SENT}")
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


# === Обработка остальных личных сообщений ===

@user_router.message(
    F.chat.type == ChatType.PRIVATE,
    ~(F.from_user.id == ADMIN_ID)
)
async def handle_private_other(message: Message) -> None:
    if photo_contest_storage.is_active:
        await message.answer(f"{Emojis.PHOTO} {Messages.PHOTO_CONTEST_ACTIVE_HINT}")
        return

    # Показываем меню с доступными действиями
    show_photo = photo_contest_storage.is_active
    await message.answer(
        f"{Emojis.INFO} Используй кнопки ниже:",
        reply_markup=get_user_reply_keyboard(show_photo=show_photo)
    )
