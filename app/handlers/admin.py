"""
Обработчики для админа.
"""

import asyncio
import logging
import random

from aiogram import Bot, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, PollAnswer
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.messages import Messages, Emojis, TEAM_NAMES
from app.callbacks import AdminCallbacks
from app.keyboards import get_admin_reply_keyboard, get_admin_menu_keyboard
from app.states import (
    GeoState,
    AdminBroadcastState,
    AdminPollState,
    AddTrackState,
)
from app.storage import (
    polls_storage,
    photo_contest_storage,
    forwarded_messages_storage,
    location_storage,
    PollData,
    PhotoEntry,
    LocationData,
)
from app.services.yandex_music import yandex_music_service
from app.constants import YANDEX_MUSIC_URL_PATTERN, MAX_PHOTO_CONTEST_PARTICIPANTS

logger = logging.getLogger(__name__)

admin_router = Router()

ADMIN_ID = settings.bot.admin_id
GROUP_ID = settings.bot.group_id

# Блокировка для предотвращения race condition при работе с photo contest
photo_contest_lock = asyncio.Lock()


# === Фильтры ===
def is_admin_private():
    return F.chat.type == ChatType.PRIVATE, F.from_user.id == ADMIN_ID


# === Команда start ===

@admin_router.message(
    CommandStart(),
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def cmd_start_admin(message: Message) -> None:
    await message.answer(
        f"{Emojis.WAVE} {Messages.WELCOME_ADMIN}",
        reply_markup=get_admin_menu_keyboard()
    )


# === Reply-кнопки ===

@admin_router.message(
    F.text == f"{Emojis.MENU} Главное меню",
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def admin_reply_menu(message: Message) -> None:
    await message.answer(
        f"{Emojis.WAVE} {Messages.ADMIN_MENU}",
        reply_markup=get_admin_reply_keyboard()
    )


# === Геопозиция ===

@admin_router.message(
    F.text == f"{Emojis.LOCATION} Геопозиция",
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def admin_reply_location(message: Message, state: FSMContext) -> None:
    location = location_storage.get()
    if location:
        await message.answer(
            Messages.LOCATION_CURRENT.format(
                latitude=location.latitude,
                longitude=location.longitude,
                address=location.address or "не указан"
            ),
            parse_mode="Markdown"
        )
    await state.set_state(GeoState.waiting_for_location)
    if not location:
        await message.answer(f"{Emojis.LOCATION} {Messages.LOCATION_REQUEST}")


@admin_router.callback_query(
    F.data == AdminCallbacks.SET_LOCATION,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_setlocation(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GeoState.waiting_for_location)
    await callback.message.answer(f"{Emojis.LOCATION} {Messages.LOCATION_REQUEST}")
    await callback.answer()


@admin_router.message(
    GeoState.waiting_for_location,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
    F.location
)
async def process_location(message: Message, state: FSMContext) -> None:
    await state.clear()
    location_storage.set(LocationData(
        latitude=message.location.latitude,
        longitude=message.location.longitude,
    ))
    await message.answer(
        f"{Emojis.SUCCESS} {Messages.LOCATION_SET_SUCCESS.format(latitude=message.location.latitude, longitude=message.location.longitude)}"
    )


@admin_router.message(
    Command("setaddress"),
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def cmd_setaddress(message: Message) -> None:
    text = message.text.replace("/setaddress", "").strip()
    if not text:
        await message.answer(Messages.ADDRESS_FORMAT)
        return
    location_storage.set_address(text)
    await message.answer(f"{Emojis.SUCCESS} {Messages.ADDRESS_SET_SUCCESS.format(address=text)}")


# === Конкурс фото ===

@admin_router.message(
    F.text == f"{Emojis.PHOTO} Фото конкурс",
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def admin_reply_photo(message: Message, bot: Bot) -> None:
    async with photo_contest_lock:
        if not photo_contest_storage.is_active:
            await _start_photo_contest(message, bot)
        else:
            await _stop_photo_contest(message, bot)


@admin_router.callback_query(
    F.data == AdminCallbacks.PHOTO_START,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_photo_start(callback: CallbackQuery, bot: Bot) -> None:
    async with photo_contest_lock:
        if photo_contest_storage.is_active:
            await callback.message.answer(f"{Emojis.WARNING} {Messages.PHOTO_CONTEST_ALREADY_ACTIVE}")
            await callback.answer()
            return
        await _start_photo_contest(callback.message, bot, from_callback=True)
        await callback.answer()


@admin_router.callback_query(
    F.data == AdminCallbacks.PHOTO_STOP,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_photo_stop(callback: CallbackQuery, bot: Bot) -> None:
    async with photo_contest_lock:
        if not photo_contest_storage.is_active:
            await callback.message.answer(f"{Emojis.WARNING} {Messages.PHOTO_CONTEST_NOT_ACTIVE}")
            await callback.answer()
            return
        await _stop_photo_contest(callback.message, bot)
        await callback.answer()


async def _start_photo_contest(message: Message, bot: Bot, from_callback: bool = False) -> None:
    photo_contest_storage.start()
    await bot.send_message(
        GROUP_ID,
        f"{Emojis.PHOTO} {Messages.PHOTO_CONTEST_STARTED}",
        parse_mode="Markdown"
    )
    msg = Messages.PHOTO_CONTEST_ADMIN_STARTED if from_callback else Messages.PHOTO_CONTEST_ADMIN_STARTED_HINT
    await message.answer(f"{Emojis.SUCCESS} {msg}")


async def _stop_photo_contest(message: Message, bot: Bot) -> None:
    photo_contest_storage.stop()

    if photo_contest_storage.is_empty():
        await message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_NO_ENTRIES}")
        await bot.send_message(GROUP_ID, f"{Emojis.PHOTO} {Messages.PHOTO_CONTEST_ENDED_EMPTY}")
        return

    await bot.send_message(
        GROUP_ID,
        f"{Emojis.PHOTO} {Messages.PHOTO_CONTEST_ENDED}",
        parse_mode="Markdown"
    )

    entries = photo_contest_storage.get_entries()

    # Отправка всех фото
    for i, (user_id, entry) in enumerate(entries, 1):
        await bot.send_photo(
            GROUP_ID,
            photo=entry.photo_id,
            caption=f"{Emojis.CAMERA} {Messages.PHOTO_CAPTION.format(num=i, user=entry.user_name)}"
        )

    # Создание опросов (макс. 10 участников в опросе)
    total_entries = len(entries)
    poll_count = (total_entries + 9) // 10  # Округление вверх

    for poll_num in range(poll_count):
        start_idx = poll_num * 10
        end_idx = min(start_idx + 10, total_entries)
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
                chat_id=GROUP_ID,
                question=poll_question,
                options=options,
                is_anonymous=False
            )

    await message.answer(
        f"{Emojis.SUCCESS} {Messages.PHOTO_CONTEST_VOTING_CREATED.format(count=photo_contest_storage.entries_count())}"
    )


# === Отправка фото на конкурс админом ===

@admin_router.callback_query(
    F.data == AdminCallbacks.SEND_PHOTO,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_send_photo(callback: CallbackQuery) -> None:
    if not photo_contest_storage.is_active:
        await callback.answer(f"{Emojis.WARNING} Конкурс фото не запущен! Сначала нажми 'Начать фото-конкурс'", show_alert=True)
        return

    user_id = callback.from_user.id
    if photo_contest_storage.has_entry(user_id):
        await callback.message.answer(f"{Emojis.WARNING} {Messages.PHOTO_ALREADY_SENT}")
    elif photo_contest_storage.entries_count() >= MAX_PHOTO_CONTEST_PARTICIPANTS:
        await callback.message.answer(f"{Emojis.ERROR} {Messages.PHOTO_CONTEST_MAX_REACHED}")
    else:
        await callback.message.answer(f"{Emojis.PHOTO} {Messages.PHOTO_SEND_PROMPT}")
    await callback.answer()


# === Обработка фото от админа ===

@admin_router.message(
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
    F.photo
)
async def handle_admin_photo(message: Message) -> None:
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
    logger.info(f"Фото для конкурса от админа {user_name}")


# === Добавление трека админом ===

@admin_router.callback_query(
    F.data == AdminCallbacks.ADD_TRACK,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_add_track(callback: CallbackQuery, state: FSMContext) -> None:
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


@admin_router.message(
    AddTrackState.waiting_for_link,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def admin_process_track_link(message: Message, state: FSMContext, bot: Bot) -> None:
    text = message.text or ""

    track_id = yandex_music_service.extract_track_id(text)
    if not track_id:
        await message.answer(f"{Emojis.ERROR} {Messages.TRACK_INVALID_LINK}")
        return

    # Показываем сообщение об обработке
    processing_msg = await message.answer(f"{Emojis.INFO} {Messages.TRACK_PROCESSING}")

    # Добавляем трек (состояние НЕ очищается, чтобы блокировать другие запросы)
    success, error, track_info = await yandex_music_service.add_track_to_playlist(track_id)

    if success and track_info:
        user = message.from_user
        user_name = f"@{user.username}" if user.username else user.full_name
        track_title = f"{track_info.artists} — {track_info.title}"

        await message.answer(
            f"{Emojis.SUCCESS} {Messages.TRACK_ADDED.format(title=track_title, user=user_name)}",
            parse_mode="Markdown"
        )
        logger.info(f"Трек {track_id} добавлен админом {user_name}")
    else:
        error_messages = {
            "connection_error": Messages.TRACK_CONNECTION_ERROR,
            "track_not_found": Messages.TRACK_NOT_FOUND,
            "playlist_not_found": Messages.PLAYLIST_ID_NOT_SET,
            "rate_limit": Messages.TRACK_RATE_LIMIT,
            "network_error": Messages.TRACK_NETWORK_ERROR,
        }
        error_msg = error_messages.get(error, "Не удалось добавить трек. Попробуйте позже.")
        await message.answer(f"{Emojis.ERROR} {error_msg}")

    # Очищаем состояние только ПОСЛЕ завершения обработки
    await state.clear()

    # Удаляем сообщение об обработке
    try:
        await processing_msg.delete()
    except:
        pass


# === Достать ножи (перенаправление на игру) ===

@admin_router.callback_query(
    F.data == AdminCallbacks.SPY,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_spy_redirect(callback: CallbackQuery) -> None:
    """Перенаправление на меню игры Достать ножи."""
    from app.keyboards import get_assassin_admin_menu
    from app.database import get_active_game, get_player_by_tg_id
    from app.messages import Messages

    game = get_active_game()
    show_register = game and game["status"] == "registration"
    admin_registered = False
    if game:
        admin_registered = get_player_by_tg_id(game["id"], ADMIN_ID) is not None

    await callback.message.edit_text(
        Messages.ASSASSIN_MENU_TITLE,
        parse_mode="Markdown",
        reply_markup=get_assassin_admin_menu(show_register, admin_registered),
    )
    await callback.answer()


# === Опросы ===

@admin_router.message(
    F.text == f"{Emojis.POLL} Опрос",
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def admin_reply_poll(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminPollState.waiting_for_poll_single)
    await message.answer(Messages.POLL_CREATE_PROMPT_SINGLE, parse_mode="Markdown")


@admin_router.callback_query(
    F.data == AdminCallbacks.POLL_SINGLE,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_poll_single(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPollState.waiting_for_poll_single)
    await callback.message.answer(Messages.POLL_CREATE_PROMPT_SINGLE, parse_mode="Markdown")
    await callback.answer()


@admin_router.callback_query(
    F.data == AdminCallbacks.POLL_MULTIPLE,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_poll_multiple(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPollState.waiting_for_poll_multiple)
    await callback.message.answer(Messages.POLL_CREATE_PROMPT_MULTIPLE, parse_mode="Markdown")
    await callback.answer()


@admin_router.message(
    AdminPollState.waiting_for_poll_single,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def process_poll_creation_single(message: Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()
    await _create_poll(message, bot, allows_multiple=False)


@admin_router.message(
    AdminPollState.waiting_for_poll_multiple,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def process_poll_creation_multiple(message: Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()
    await _create_poll(message, bot, allows_multiple=True)


async def _create_poll(message: Message, bot: Bot, allows_multiple: bool) -> None:
    """Создаёт опрос в группе."""
    text = message.text.strip()
    if "|" not in text:
        await message.answer(f"{Emojis.ERROR} {Messages.POLL_INVALID_FORMAT}")
        return

    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        await message.answer(Messages.POLL_MIN_OPTIONS)
        return

    question = parts[0]
    options = parts[1:]

    if len(options) > 10:
        await message.answer(Messages.POLL_MAX_OPTIONS)
        return

    try:
        poll_message = await bot.send_poll(
            chat_id=GROUP_ID,
            question=question,
            options=options,
            is_anonymous=False,
            allows_multiple_answers=allows_multiple
        )

        polls_storage.add(
            poll_message.poll.id,
            PollData(question=question, options=options, allows_multiple=allows_multiple)
        )

        mode = Messages.POLL_MODE_MULTIPLE if allows_multiple else Messages.POLL_MODE_SINGLE
        await message.answer(f"{Emojis.SUCCESS} {Messages.POLL_CREATED_MODE.format(mode=mode)}")
    except Exception as e:
        await message.answer(Messages.POLL_ERROR.format(error=str(e)))


@admin_router.callback_query(
    F.data == AdminCallbacks.POLL_RESULTS,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_poll_results(callback: CallbackQuery) -> None:
    if polls_storage.is_empty():
        await callback.message.answer(f"{Emojis.POLL} {Messages.POLL_NO_POLLS}")
        await callback.answer()
        return

    results = f"{Emojis.POLL} {Messages.POLL_RESULTS_TITLE}"

    for poll_id, poll_data in polls_storage.get_all().items():
        results += f"❓ *{poll_data.question}*\n"

        vote_counts: dict[int, list[str]] = {}
        for user, option_ids in poll_data.votes.items():
            for opt_id in option_ids:
                if opt_id not in vote_counts:
                    vote_counts[opt_id] = []
                vote_counts[opt_id].append(user)

        for i, option in enumerate(poll_data.options):
            users = vote_counts.get(i, [])
            count = len(users)
            results += f"  • {option}: {count}\n"

        results += "\n"

    await callback.message.answer(results, parse_mode="Markdown")
    await callback.answer()


# === Broadcast ===

@admin_router.message(
    F.text == f"{Emojis.BROADCAST} Сообщение",
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def admin_reply_broadcast(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastState.waiting_for_text)
    await message.answer(f"{Emojis.BROADCAST} {Messages.BROADCAST_PROMPT}")


@admin_router.callback_query(
    F.data == AdminCallbacks.BROADCAST,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastState.waiting_for_text)
    await callback.message.answer(f"{Emojis.BROADCAST} {Messages.BROADCAST_PROMPT}")
    await callback.answer()


@admin_router.message(
    AdminBroadcastState.waiting_for_text,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def process_broadcast(message: Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()

    try:
        await bot.send_message(GROUP_ID, f"{Emojis.BROADCAST} {message.text}")
        await message.answer(f"{Emojis.SUCCESS} {Messages.BROADCAST_SENT}")
    except Exception as e:
        await message.answer(Messages.BROADCAST_ERROR.format(error=str(e)))


# === Ответы на пересланные сообщения ===

@admin_router.message(
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
    F.reply_to_message
)
async def handle_admin_reply(message: Message, bot: Bot) -> None:
    reply_to = message.reply_to_message

    if not forwarded_messages_storage.exists(reply_to.message_id):
        return

    original = forwarded_messages_storage.get(reply_to.message_id)

    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            text=f"{Emojis.MESSAGE} {message.text}",
            reply_to_message_id=original.message_id
        )
        await message.answer(Messages.ASK_REPLY_SENT)
    except Exception as e:
        await message.answer(Messages.ASK_REPLY_ERROR.format(error=str(e)))


# === Обработка голосов в опросах ===

@admin_router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer) -> None:
    poll_id = poll_answer.poll_id

    if not polls_storage.exists(poll_id):
        return

    user = poll_answer.user
    user_name = f"@{user.username}" if user.username else user.full_name

    polls_storage.update_vote(poll_id, user_name, list(poll_answer.option_ids))
