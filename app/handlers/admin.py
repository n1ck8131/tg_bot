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
from app.messages import Messages, ButtonLabels, Emojis, TEAM_NAMES
from app.callbacks import AdminCallbacks
from app.keyboards import get_admin_reply_keyboard, get_admin_menu_keyboard
from app.states import (
    GeoState,
    AdminBroadcastState,
    AdminPollState,
)
from app.storage import (
    polls_storage,
    photo_contest_storage,
    forwarded_messages_storage,
    location_storage,
    PollData,
    LocationData,
)
from app.services.yandex_music import yandex_music_service, process_track_submission
from app.services.photo_contest import handle_photo_submission, stop_photo_submissions, start_voting, end_voting
from app.constants import YANDEX_MUSIC_URL_PATTERN, MAX_PHOTO_CONTEST_PARTICIPANTS

logger = logging.getLogger(__name__)

admin_router = Router()

ADMIN_ID = settings.bot.admin_id
GROUP_ID = settings.bot.group_id

# Блокировка для предотвращения race condition при работе с photo contest
photo_contest_lock = asyncio.Lock()

# Буфер для альбомов (media group) от админа
_media_group_buffer: dict[str, list[Message]] = {}
_media_group_tasks: dict[str, asyncio.Task] = {}


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


# === Инфо о регистрации ===

@admin_router.message(
    F.text == f"{Emojis.INFO} {ButtonLabels.REG_INFO}",
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def admin_reply_reg_info(message: Message) -> None:
    """Показать сводку: кто зарегистрирован в игру и кто отправил фото."""
    from app.database import get_active_game, get_all_players

    text = Messages.REG_INFO_TITLE

    # --- Секция "Достать ножи" ---
    text += Messages.REG_INFO_GAME_SECTION
    game = get_active_game()
    if not game:
        text += Messages.REG_INFO_GAME_NO_ACTIVE
    elif game["status"] == "running":
        text += Messages.REG_INFO_GAME_RUNNING
    else:
        players = get_all_players(game["id"])
        text += Messages.REG_INFO_GAME_PLAYERS.format(count=len(players))
        for player in players:
            name = player["display_name"]
            if player["is_virtual"]:
                name += " (виртуальный)"
            text += Messages.REG_INFO_GAME_PLAYER_ENTRY.format(name=name)
        if not players:
            text += "  Пока никого\n"

    # --- Секция "Фото-конкурс" ---
    text += Messages.REG_INFO_PHOTO_SECTION
    async with photo_contest_lock:
        if not photo_contest_storage.is_active and not photo_contest_storage.is_voting_active and photo_contest_storage.is_empty():
            text += Messages.REG_INFO_PHOTO_NOT_ACTIVE
        elif photo_contest_storage.is_voting_active:
            text += Messages.REG_INFO_PHOTO_VOTING
            entries = photo_contest_storage.get_entries()
            text += Messages.REG_INFO_PHOTO_ENTRIES.format(count=len(entries))
            for _user_id, entry in entries:
                text += Messages.REG_INFO_PHOTO_ENTRY.format(name=entry.user_name)
        else:
            entries = photo_contest_storage.get_entries()
            count = len(entries)
            text += Messages.REG_INFO_PHOTO_ENTRIES.format(count=count)
            for _user_id, entry in entries:
                text += Messages.REG_INFO_PHOTO_ENTRY.format(name=entry.user_name)
            if count == 0:
                text += "  Пока никого\n"

    await message.answer(text, parse_mode="Markdown")


@admin_router.callback_query(
    F.data == AdminCallbacks.REG_INFO,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_reg_info(callback: CallbackQuery) -> None:
    """Показать сводку по регистрациям (inline-кнопка)."""
    from app.database import get_active_game, get_all_players

    text = Messages.REG_INFO_TITLE

    # --- Секция "Достать ножи" ---
    text += Messages.REG_INFO_GAME_SECTION
    game = get_active_game()
    if not game:
        text += Messages.REG_INFO_GAME_NO_ACTIVE
    elif game["status"] == "running":
        text += Messages.REG_INFO_GAME_RUNNING
    else:
        players = get_all_players(game["id"])
        text += Messages.REG_INFO_GAME_PLAYERS.format(count=len(players))
        for player in players:
            name = player["display_name"]
            if player["is_virtual"]:
                name += " (виртуальный)"
            text += Messages.REG_INFO_GAME_PLAYER_ENTRY.format(name=name)
        if not players:
            text += "  Пока никого\n"

    # --- Секция "Фото-конкурс" ---
    text += Messages.REG_INFO_PHOTO_SECTION
    async with photo_contest_lock:
        if not photo_contest_storage.is_active and not photo_contest_storage.is_voting_active and photo_contest_storage.is_empty():
            text += Messages.REG_INFO_PHOTO_NOT_ACTIVE
        elif photo_contest_storage.is_voting_active:
            text += Messages.REG_INFO_PHOTO_VOTING
            entries = photo_contest_storage.get_entries()
            text += Messages.REG_INFO_PHOTO_ENTRIES.format(count=len(entries))
            for _user_id, entry in entries:
                text += Messages.REG_INFO_PHOTO_ENTRY.format(name=entry.user_name)
        else:
            entries = photo_contest_storage.get_entries()
            count = len(entries)
            text += Messages.REG_INFO_PHOTO_ENTRIES.format(count=count)
            for _user_id, entry in entries:
                text += Messages.REG_INFO_PHOTO_ENTRY.format(name=entry.user_name)
            if count == 0:
                text += "  Пока никого\n"

    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()


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

    if not location_storage.is_set():
        await message.answer(f"{Emojis.ERROR} Сначала установите координаты через меню бота.")
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
    """
    Управление фото-конкурсом через reply-кнопку.
    Переключает между состояниями:
    1. Не активен -> Начать приём фото
    2. Приём активен -> Завершить приём фото
    3. Приём завершён -> Начать голосование
    4. Голосование идёт -> Завершить голосование
    """
    async with photo_contest_lock:
        if photo_contest_storage.is_voting_active:
            # Голосование идёт -> завершить
            await end_voting(message, bot, GROUP_ID)
        elif photo_contest_storage.is_active:
            # Приём фото идёт -> завершить приём
            await stop_photo_submissions(message, bot, GROUP_ID)
        elif not photo_contest_storage.is_empty():
            # Есть фото, но приём завершён -> начать голосование
            await start_voting(message, bot, GROUP_ID)
        else:
            # Конкурс не активен -> начать приём фото
            await _start_photo_contest(message, bot)


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
    """Завершить приём фото."""
    async with photo_contest_lock:
        if not photo_contest_storage.is_active:
            await callback.message.answer(f"{Emojis.WARNING} {Messages.PHOTO_CONTEST_NOT_ACTIVE}")
            await callback.answer()
            return
        await stop_photo_submissions(callback.message, bot, GROUP_ID)
        await callback.answer()


@admin_router.callback_query(
    F.data == AdminCallbacks.PHOTO_START_VOTING,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_photo_start_voting(callback: CallbackQuery, bot: Bot) -> None:
    """Начать голосование (автоматически закрывает приём фото)."""
    async with photo_contest_lock:
        if photo_contest_storage.is_voting_active:
            await callback.message.answer(f"{Emojis.WARNING} {Messages.PHOTO_VOTING_ALREADY_ACTIVE}")
            await callback.answer()
            return
        # Автоматически закрываем приём фото, если он активен
        if photo_contest_storage.is_active:
            photo_contest_storage.stop()
        await start_voting(callback.message, bot, GROUP_ID)
        await callback.answer()


@admin_router.callback_query(
    F.data == AdminCallbacks.PHOTO_END_VOTING,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_photo_end_voting(callback: CallbackQuery, bot: Bot) -> None:
    """Завершить голосование."""
    async with photo_contest_lock:
        if not photo_contest_storage.is_voting_active:
            await callback.message.answer(f"{Emojis.WARNING} {Messages.PHOTO_VOTING_NOT_ACTIVE}")
            await callback.answer()
            return
        await end_voting(callback.message, bot, GROUP_ID)
        await callback.answer()


async def _start_photo_contest(message: Message, bot: Bot, from_callback: bool = False) -> None:
    """Начать приём фото."""
    photo_contest_storage.start()
    await bot.send_message(
        GROUP_ID,
        f"{Emojis.PHOTO} {Messages.PHOTO_CONTEST_STARTED}",
        parse_mode="Markdown"
    )
    msg = Messages.PHOTO_CONTEST_ADMIN_STARTED if from_callback else Messages.PHOTO_CONTEST_ADMIN_STARTED_HINT
    await message.answer(f"{Emojis.SUCCESS} {msg}")


# === Отправка фото на конкурс админом ===

@admin_router.callback_query(
    F.data == AdminCallbacks.SEND_PHOTO,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_send_photo(callback: CallbackQuery) -> None:
    """Приглашение отправить фото. Админ может отправлять несколько фото для тестирования."""
    if not photo_contest_storage.is_active:
        await callback.answer(f"{Emojis.WARNING} {Messages.PHOTO_CONTEST_NOT_STARTED_ADMIN}", show_alert=True)
        return

    # Админ может отправлять неограниченное количество фото для тестирования
    count = photo_contest_storage.entries_count()
    await callback.message.answer(
        f"{Emojis.PHOTO} {Messages.PHOTO_SEND_PROMPT}\n\n"
        f"Сейчас в конкурсе: {count} фото"
    )
    await callback.answer()


# === Обработка фото от админа ===

@admin_router.message(
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
    F.photo
)
async def handle_admin_photo(message: Message) -> None:
    """Обработка фото от админа. Поддерживает альбомы (media group)."""
    if message.media_group_id:
        mg_id = message.media_group_id
        if mg_id not in _media_group_buffer:
            _media_group_buffer[mg_id] = []
        _media_group_buffer[mg_id].append(message)

        # Отменить предыдущий таск, если есть (ждём пока все фото альбома придут)
        if mg_id in _media_group_tasks:
            _media_group_tasks[mg_id].cancel()

        _media_group_tasks[mg_id] = asyncio.create_task(
            _process_admin_media_group(mg_id)
        )
    else:
        await handle_photo_submission(message, is_admin=True)


async def _process_admin_media_group(mg_id: str) -> None:
    """Обрабатывает альбом фото от админа после небольшой задержки."""
    await asyncio.sleep(0.5)

    messages = _media_group_buffer.pop(mg_id, [])
    _media_group_tasks.pop(mg_id, None)

    if not messages:
        return

    count = 0
    for msg in messages:
        result = await handle_photo_submission(msg, is_admin=True, silent=True)
        if result:
            count += 1

    if count > 0:
        await messages[0].answer(
            f"{Emojis.SUCCESS} {Messages.PHOTO_ALBUM_ACCEPTED.format(count=count)}"
            f" (всего: {photo_contest_storage.entries_count()})"
        )


# === Добавление трека админом ===

@admin_router.message(
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
    F.text.regexp(YANDEX_MUSIC_URL_PATTERN)
)
async def admin_handle_yandex_link(message: Message) -> None:
    """Автоматическая обработка ссылок на Яндекс.Музыку от админа."""
    if not yandex_music_service.is_configured:
        await message.answer(f"{Emojis.ERROR} {Messages.PLAYLIST_NOT_CONFIGURED}")
        return

    await process_track_submission(message, is_admin=True)


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
