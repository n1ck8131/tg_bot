"""
Обработчики для группового чата.
"""

import logging
import re

from aiogram import Bot, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.messages import Messages, Emojis
from app.callbacks import MenuCallbacks, PhotoVoteCallbacks
from app.keyboards import get_main_menu_keyboard
from app.states import AskState
from app.storage import (
    location_storage,
    forwarded_messages_storage,
    photo_contest_storage,
    ForwardedMessage,
)
from app.constants import (
    BIRTHDAY_PHOTO_1,
    BIRTHDAY_PHOTO_2,
)

logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """Экранирует специальные символы Markdown для безопасной вставки пользовательского текста."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(r'([%s])' % re.escape(escape_chars), r'\\\1', text)

group_router = Router()


# === Обработка фото в группе ===

@group_router.message(F.chat.id == settings.bot.group_id, F.photo)
async def handle_group_photo(message: Message, bot: Bot) -> None:
    """Напоминает, что фото нужно отправлять в личный чат."""
    if photo_contest_storage.is_active:
        bot_username = (await bot.get_me()).username
        safe_username = bot_username.replace("_", "\\_")
        await message.reply(
            f"{Emojis.WARNING} {Messages.PHOTO_CONTEST_SEND_TO_PRIVATE}\n\n"
            f"Напиши @{safe_username} в личку и отправь фото там.",
            parse_mode="Markdown"
        )
    # Если конкурс не активен - игнорируем


# === Команды ===

@group_router.message(CommandStart(), F.chat.id == settings.bot.group_id)
async def cmd_start_group(message: Message) -> None:
    await message.answer(
        f"{Emojis.WAVE} {Messages.WELCOME_GROUP}",
        reply_markup=get_main_menu_keyboard()
    )


@group_router.message(Command("menu"), F.chat.id == settings.bot.group_id)
async def cmd_menu(message: Message) -> None:
    await message.answer(
        f"{Emojis.HELP} {Messages.MAIN_MENU}",
        reply_markup=get_main_menu_keyboard()
    )


@group_router.message(Command("birthday"), F.chat.id == settings.bot.group_id)
async def cmd_birthday(message: Message) -> None:
    info = settings.content.birthday_info.replace("\\n", "\n")
    caption_text = f"{Emojis.BIRTHDAY} {Messages.BIRTHDAY_TEMPLATE.format(info=info)}"

    # Отправляем медиа-группу с фото
    media_group = [
        InputMediaPhoto(
            media=FSInputFile(BIRTHDAY_PHOTO_1),
            caption=caption_text,
            parse_mode="Markdown"
        ),
        InputMediaPhoto(media=FSInputFile(BIRTHDAY_PHOTO_2))
    ]
    await message.answer_media_group(media=media_group)


@group_router.message(Command("trip"), F.chat.id == settings.bot.group_id)
async def cmd_trip(message: Message) -> None:
    info = settings.content.trip_info.replace("\\n", "\n")
    await message.answer(
        f"{Emojis.TRIP} {Messages.TRIP_TEMPLATE.format(info=info)}",
        parse_mode="Markdown"
    )


@group_router.message(Command("wishlist"), F.chat.id == settings.bot.group_id)
async def cmd_wishlist(message: Message) -> None:
    await message.answer(
        f"{Emojis.WISHLIST} {Messages.WISHLIST_TEMPLATE.format(url=settings.content.wishlist_url)}",
        parse_mode="Markdown"
    )


@group_router.message(Command("location"), F.chat.id == settings.bot.group_id)
async def cmd_location(message: Message) -> None:
    location = location_storage.get()
    if location:
        await message.answer_location(
            latitude=location.latitude,
            longitude=location.longitude
        )
        if location.address:
            await message.answer(f"{Emojis.LOCATION} {location.address}")
    else:
        await message.answer(f"{Emojis.LOCATION} {Messages.LOCATION_NOT_SET}")


@group_router.message(Command("help"), F.chat.id == settings.bot.group_id)
async def cmd_help_group(message: Message) -> None:
    await message.answer(
        Messages.HELP_TEXT,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


@group_router.message(Command("ask"), F.chat.id == settings.bot.group_id)
async def cmd_ask(message: Message, state: FSMContext) -> None:
    await state.set_state(AskState.waiting_for_question)
    await message.reply(f"✏️ {Messages.ASK_PROMPT}")


@group_router.message(AskState.waiting_for_question, F.chat.id == settings.bot.group_id)
async def process_question(message: Message, bot: Bot, state: FSMContext) -> None:
    await state.clear()

    text = message.text
    if not text:
        return

    user = message.from_user
    user_display = user.full_name
    if user.username:
        user_display += f" (@{user.username})"

    # Экранируем пользовательский текст для безопасной вставки в Markdown
    safe_user_display = escape_markdown(user_display)
    safe_text = escape_markdown(text)

    forward_text = (
        f"{Emojis.FORWARD} {Messages.ASK_FORWARD_TEMPLATE.format(user=safe_user_display, text=safe_text)}"
    )

    try:
        sent = await bot.send_message(
            settings.bot.admin_id,
            forward_text,
            parse_mode="Markdown"
        )
        forwarded_messages_storage.add(
            sent.message_id,
            ForwardedMessage(
                message_id=message.message_id,
                chat_id=message.chat.id,
                user_id=user.id,
                user_name=user_display
            )
        )
        await message.answer(f"{Emojis.SUCCESS} {Messages.ASK_SUCCESS}")
    except Exception as e:
        logger.error(f"Ошибка при пересылке админу: {e}")
        await message.answer(
            f"{Emojis.ERROR} Не удалось отправить вопрос. Попробуйте позже."
        )


# === Callback обработчики ===

@group_router.callback_query(F.data == MenuCallbacks.BIRTHDAY)
async def callback_birthday(callback: CallbackQuery) -> None:
    info = settings.content.birthday_info.replace("\\n", "\n")
    caption_text = f"{Emojis.BIRTHDAY} {Messages.BIRTHDAY_TEMPLATE.format(info=info)}"

    # Отправляем медиа-группу с фото
    media_group = [
        InputMediaPhoto(
            media=FSInputFile(BIRTHDAY_PHOTO_1),
            caption=caption_text,
            parse_mode="Markdown"
        ),
        InputMediaPhoto(media=FSInputFile(BIRTHDAY_PHOTO_2))
    ]
    await callback.message.answer_media_group(media=media_group)
    await callback.answer()


@group_router.callback_query(F.data == MenuCallbacks.TRIP)
async def callback_trip(callback: CallbackQuery) -> None:
    info = settings.content.trip_info.replace("\\n", "\n")
    await callback.message.answer(
        f"{Emojis.TRIP} {Messages.TRIP_TEMPLATE.format(info=info)}",
        parse_mode="Markdown"
    )
    await callback.answer()


@group_router.callback_query(F.data == MenuCallbacks.WISHLIST)
async def callback_wishlist(callback: CallbackQuery) -> None:
    await callback.message.answer(
        f"{Emojis.WISHLIST} {Messages.WISHLIST_TEMPLATE.format(url=settings.content.wishlist_url)}",
        parse_mode="Markdown"
    )
    await callback.answer()


@group_router.callback_query(F.data == MenuCallbacks.LOCATION)
async def callback_location(callback: CallbackQuery) -> None:
    location = location_storage.get()
    if location:
        await callback.message.answer_location(
            latitude=location.latitude,
            longitude=location.longitude
        )
        if location.address:
            await callback.message.answer(f"{Emojis.LOCATION} {location.address}")
    else:
        await callback.message.answer(f"{Emojis.LOCATION} {Messages.LOCATION_NOT_SET}")
    await callback.answer()


@group_router.callback_query(F.data == MenuCallbacks.ASK)
async def callback_ask(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AskState.waiting_for_question)
    await callback.message.answer(f"✏️ {Messages.ASK_PROMPT}")
    await callback.answer()


@group_router.callback_query(F.data == MenuCallbacks.PLAYLIST)
async def callback_playlist(callback: CallbackQuery) -> None:
    await callback.message.answer(
        f"{Emojis.MUSIC} {Messages.PLAYLIST_INFO_GROUP}",
        parse_mode="Markdown"
    )
    await callback.answer()


@group_router.callback_query(F.data == MenuCallbacks.HELP)
async def callback_help(callback: CallbackQuery) -> None:
    await callback.message.answer(Messages.HELP_TEXT, parse_mode="Markdown")
    await callback.answer()


# === Фото-конкурс: голосование ===

@group_router.callback_query(F.data.startswith(PhotoVoteCallbacks.PREFIX))
async def callback_photo_vote(callback: CallbackQuery) -> None:
    """Обработка голосования за фото."""
    if not photo_contest_storage.is_voting_active:
        await callback.answer(f"{Emojis.WARNING} Голосование не активно!", show_alert=True)
        return

    # Извлечь user_id владельца фото из callback_data
    # Формат: "photo_vote:<user_id>"
    try:
        photo_owner_id = int(callback.data.split(":")[-1])
    except (ValueError, IndexError):
        await callback.answer(f"{Emojis.ERROR} Ошибка обработки голоса", show_alert=True)
        logger.error(f"Неверный формат callback_data: {callback.data}")
        return

    voter_id = callback.from_user.id

    # Проверка: нельзя голосовать за себя
    if voter_id == photo_owner_id:
        await callback.answer(Messages.PHOTO_VOTE_OWN, show_alert=True)
        return

    # Проверка: можно голосовать только один раз
    if photo_contest_storage.has_voted(voter_id):
        await callback.answer(Messages.PHOTO_VOTE_ALREADY, show_alert=True)
        return

    # Получить имя владельца фото
    entries = photo_contest_storage.get_entries()
    photo_owner_name = None
    for user_id, entry in entries:
        if user_id == photo_owner_id:
            photo_owner_name = entry.user_name
            break

    if not photo_owner_name:
        await callback.answer(f"{Emojis.ERROR} Фото не найдено", show_alert=True)
        return

    # Добавить голос
    photo_contest_storage.add_vote(voter_id, photo_owner_id)

    # Показать всплывающее окно с подтверждением
    await callback.answer(
        Messages.PHOTO_VOTE_SUCCESS.format(user=photo_owner_name),
        show_alert=True
    )
    logger.info(f"Пользователь {voter_id} проголосовал за фото от {photo_owner_id}")
