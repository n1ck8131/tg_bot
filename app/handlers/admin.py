"""
Обработчики для админа.
"""

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
from app.keyboards import get_admin_reply_keyboard
from app.states import (
    GeoState,
    AdminBroadcastState,
    AdminPollState,
    AdminBeerpongState,
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

logger = logging.getLogger(__name__)

admin_router = Router()

ADMIN_ID = settings.bot.admin_id
GROUP_ID = settings.bot.group_id


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
        reply_markup=get_admin_reply_keyboard()
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
    if not photo_contest_storage.is_active:
        await _start_photo_contest(message, bot)
    else:
        await _stop_photo_contest(message, bot)


@admin_router.callback_query(
    F.data == AdminCallbacks.PHOTO_START,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_photo_start(callback: CallbackQuery, bot: Bot) -> None:
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
    options = []

    for i, (user_id, entry) in enumerate(entries, 1):
        await bot.send_photo(
            GROUP_ID,
            photo=entry.photo_id,
            caption=f"{Emojis.CAMERA} {Messages.PHOTO_CAPTION.format(num=i, user=entry.user_name)}"
        )
        options.append(Messages.PHOTO_OPTION.format(num=i, user=entry.user_name))

    if len(options) >= 2:
        await bot.send_poll(
            chat_id=GROUP_ID,
            question=f"{Emojis.TROPHY} {Messages.PHOTO_CONTEST_VOTE_QUESTION}",
            options=options[:10],
            is_anonymous=False
        )

    await message.answer(
        f"{Emojis.SUCCESS} {Messages.PHOTO_CONTEST_VOTING_CREATED.format(count=photo_contest_storage.entries_count())}"
    )


# === Бир-понг ===

@admin_router.message(
    F.text == f"{Emojis.BEERPONG} Бир-понг",
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def admin_reply_beerpong(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminBeerpongState.waiting_for_participants)
    await message.answer(Messages.BEERPONG_PROMPT, parse_mode="Markdown")


@admin_router.callback_query(
    F.data == AdminCallbacks.BEERPONG,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_beerpong(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBeerpongState.waiting_for_participants)
    await callback.message.answer(Messages.BEERPONG_PROMPT, parse_mode="Markdown")
    await callback.answer()


@admin_router.message(
    AdminBeerpongState.waiting_for_participants,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def process_beerpong_participants(message: Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()

    participants = [p.strip() for p in message.text.split(",") if p.strip()]

    if len(participants) < 2:
        await message.answer(Messages.BEERPONG_MIN_PARTICIPANTS)
        return

    random.shuffle(participants)
    mid = len(participants) // 2
    team1 = participants[:mid]
    team2 = participants[mid:]
    team_names = random.choice(TEAM_NAMES)

    await bot.send_message(
        GROUP_ID,
        f"{Emojis.BEERPONG} {Messages.BEERPONG_ANNOUNCEMENT.format(team1_name=f'{Emojis.TEAM_RED} {team_names[0]}', team1_members=', '.join(team1), team2_name=f'{Emojis.TEAM_BLUE} {team_names[1]}', team2_members=', '.join(team2))}",
        parse_mode="Markdown"
    )
    await message.answer(f"{Emojis.SUCCESS} {Messages.BEERPONG_TEAMS_CREATED}")


# === Шпион ===

@admin_router.message(
    F.text == f"{Emojis.SPY} Шпион",
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def admin_reply_spy(message: Message, bot: Bot) -> None:
    await bot.send_message(
        GROUP_ID,
        f"{Emojis.SPY} {Messages.SPY_ANNOUNCEMENT}",
        parse_mode="Markdown"
    )
    await message.answer(f"{Emojis.SUCCESS} {Messages.SPY_STARTED}")


@admin_router.callback_query(
    F.data == AdminCallbacks.SPY,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_spy(callback: CallbackQuery, bot: Bot) -> None:
    await bot.send_message(
        GROUP_ID,
        f"{Emojis.SPY} {Messages.SPY_ANNOUNCEMENT}",
        parse_mode="Markdown"
    )
    await callback.message.answer(f"{Emojis.SUCCESS} {Messages.SPY_STARTED}")
    await callback.answer()


# === Опросы ===

@admin_router.message(
    F.text == f"{Emojis.POLL} Опрос",
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def admin_reply_poll(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminPollState.waiting_for_poll)
    await message.answer(Messages.POLL_CREATE_PROMPT, parse_mode="Markdown")


@admin_router.callback_query(
    F.data == AdminCallbacks.POLL,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_poll(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPollState.waiting_for_poll)
    await callback.message.answer(Messages.POLL_CREATE_PROMPT, parse_mode="Markdown")
    await callback.answer()


@admin_router.message(
    AdminPollState.waiting_for_poll,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID
)
async def process_poll_creation(message: Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()

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
            allows_multiple_answers=False
        )

        polls_storage.add(
            poll_message.poll.id,
            PollData(question=question, options=options)
        )

        await message.answer(f"{Emojis.SUCCESS} {Messages.POLL_CREATED}")
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
