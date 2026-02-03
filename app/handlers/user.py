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
from app.constants import MAX_PHOTO_CONTEST_PARTICIPANTS
from app.messages import Messages, Emojis
from app.callbacks import UserCallbacks
from app.keyboards import get_user_menu_keyboard
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
    await message.answer(
        Messages.WELCOME_USER,
        parse_mode="Markdown",
        reply_markup=get_user_menu_keyboard()
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
        elif photo_contest_storage.entries_count() >= MAX_PHOTO_CONTEST_PARTICIPANTS:
            await callback.message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_MAX_REACHED}")
        else:
            await callback.message.answer(f"{Emojis.PHOTO} {Messages.PHOTO_SEND_PROMPT}")
    else:
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

    # Показываем сообщение об обработке
    processing_msg = await message.answer(f"{Emojis.INFO} {Messages.TRACK_PROCESSING}")

    # Обрабатываем трек (состояние НЕ очищается, чтобы блокировать другие запросы)
    await _add_track_to_playlist(message, track_id)

    # Очищаем состояние только ПОСЛЕ завершения обработки
    await state.clear()

    # Удаляем сообщение об обработке
    try:
        await processing_msg.delete()
    except Exception as e:
        logger.debug(f"Failed to delete processing message: {e}")


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
            "unexpected_error": "Произошла ошибка. Попробуйте позже.",
            "max_retries": "Превышено количество попыток. Попробуйте позже.",
        }
        # Используем generic message для неизвестных ошибок
        error_msg = error_messages.get(error, "Не удалось добавить трек. Попробуйте позже.")
        await message.answer(f"{Emojis.ERROR} {error_msg}")


# === Обработка фото для конкурса ===

@user_router.message(
    F.chat.type == ChatType.PRIVATE,
    F.photo
)
async def handle_private_photo(message: Message) -> None:
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


# === Обработка остальных личных сообщений ===

@user_router.message(
    F.chat.type == ChatType.PRIVATE,
    ~(F.from_user.id == ADMIN_ID)
)
async def handle_private_other(message: Message) -> None:
    # Показываем меню с доступными действиями
    await message.answer(
        f"{Emojis.INFO} Используй кнопки из меню выше или набери /start",
        reply_markup=get_user_menu_keyboard()
    )
