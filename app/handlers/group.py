"""
Обработчики для группового чата.
"""

import logging

from aiogram import Bot, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.messages import Messages, Emojis
from app.callbacks import MenuCallbacks
from app.keyboards import get_main_menu_keyboard
from app.states import AskState
from app.storage import (
    location_storage,
    forwarded_messages_storage,
    ForwardedMessage,
)

logger = logging.getLogger(__name__)

group_router = Router()


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
    await message.answer(
        f"{Emojis.BIRTHDAY} {Messages.BIRTHDAY_TEMPLATE.format(info=info)}",
        parse_mode="Markdown"
    )


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

    forward_text = (
        f"{Emojis.FORWARD} {Messages.ASK_FORWARD_TEMPLATE.format(user=user_display, text=text)}"
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


# === Callback обработчики ===

@group_router.callback_query(F.data == MenuCallbacks.BIRTHDAY)
async def callback_birthday(callback: CallbackQuery) -> None:
    info = settings.content.birthday_info.replace("\\n", "\n")
    await callback.message.answer(
        f"{Emojis.BIRTHDAY} {Messages.BIRTHDAY_TEMPLATE.format(info=info)}",
        parse_mode="Markdown"
    )
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
