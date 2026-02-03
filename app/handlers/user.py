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
from app.keyboards import get_user_menu_keyboard
from app.states import AddTrackState
from app.services.yandex_music import yandex_music_service, process_track_submission
from app.services.photo_contest import handle_photo_submission

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
    await process_track_submission(message, state, is_admin=False)


# === Обработка фото для конкурса ===

@user_router.message(
    F.chat.type == ChatType.PRIVATE,
    F.photo
)
async def handle_private_photo(message: Message) -> None:
    await handle_photo_submission(message)


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
