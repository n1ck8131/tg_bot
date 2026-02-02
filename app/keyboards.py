"""
Клавиатуры бота.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from app.callbacks import MenuCallbacks, AdminCallbacks, UserCallbacks
from app.messages import ButtonLabels, Emojis
from app.storage import photo_contest_storage


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню с inline-кнопками."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{Emojis.BIRTHDAY} {ButtonLabels.BIRTHDAY}",
                callback_data=MenuCallbacks.BIRTHDAY
            ),
            InlineKeyboardButton(
                text=f"{Emojis.TRIP} {ButtonLabels.TRIP}",
                callback_data=MenuCallbacks.TRIP
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.WISHLIST} {ButtonLabels.WISHLIST}",
                callback_data=MenuCallbacks.WISHLIST
            ),
            InlineKeyboardButton(
                text=f"{Emojis.LOCATION} {ButtonLabels.LOCATION}",
                callback_data=MenuCallbacks.LOCATION
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.ASK} {ButtonLabels.ASK}",
                callback_data=MenuCallbacks.ASK
            ),
            InlineKeyboardButton(
                text=f"{Emojis.PLAYLIST} {ButtonLabels.PLAYLIST}",
                callback_data=MenuCallbacks.PLAYLIST
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.HELP} {ButtonLabels.HELP}",
                callback_data=MenuCallbacks.HELP
            ),
        ],
    ])


def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Постоянная клавиатура для админа."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=f"{Emojis.PHOTO} {ButtonLabels.PHOTO_CONTEST}"),
                KeyboardButton(text=f"{Emojis.BEERPONG} {ButtonLabels.BEERPONG}"),
            ],
            [
                KeyboardButton(text=f"{Emojis.SPY} {ButtonLabels.SPY}"),
                KeyboardButton(text=f"{Emojis.LOCATION} {ButtonLabels.LOCATION}"),
            ],
            [
                KeyboardButton(text=f"{Emojis.POLL} {ButtonLabels.POLL}"),
                KeyboardButton(text=f"{Emojis.BROADCAST} {ButtonLabels.MESSAGE}"),
            ],
            [
                KeyboardButton(text=f"{Emojis.MENU} {ButtonLabels.MAIN_MENU}"),
            ],
        ],
        resize_keyboard=True,
        persistent=True
    )


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню админа в личке."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{Emojis.LOCATION} {ButtonLabels.SET_LOCATION}",
                callback_data=AdminCallbacks.SET_LOCATION
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.PHOTO} {ButtonLabels.PHOTO_START}",
                callback_data=AdminCallbacks.PHOTO_START
            ),
            InlineKeyboardButton(
                text=f"{Emojis.ERROR} {ButtonLabels.PHOTO_STOP}",
                callback_data=AdminCallbacks.PHOTO_STOP
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.BEERPONG} {ButtonLabels.BEERPONG}",
                callback_data=AdminCallbacks.BEERPONG
            ),
            InlineKeyboardButton(
                text=f"{Emojis.SPY} {ButtonLabels.SPY}",
                callback_data=AdminCallbacks.SPY
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.POLL} {ButtonLabels.CREATE_POLL}",
                callback_data=AdminCallbacks.POLL
            ),
            InlineKeyboardButton(
                text=f"📈 {ButtonLabels.POLL_RESULTS}",
                callback_data=AdminCallbacks.POLL_RESULTS
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.BROADCAST} {ButtonLabels.BROADCAST}",
                callback_data=AdminCallbacks.BROADCAST
            ),
        ],
    ])


def get_user_reply_keyboard(show_photo: bool = False) -> ReplyKeyboardMarkup:
    """Постоянная клавиатура для пользователей."""
    buttons = []
    if show_photo:
        buttons.append([KeyboardButton(text=f"{Emojis.PHOTO} {ButtonLabels.SEND_PHOTO}")])
    buttons.append([KeyboardButton(text=f"{Emojis.MUSIC} {ButtonLabels.ADD_TRACK}")])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        persistent=True
    )


def get_user_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню пользователя в личке."""
    buttons = []
    if photo_contest_storage.is_active:
        buttons.append([
            InlineKeyboardButton(
                text=f"{Emojis.PHOTO} {ButtonLabels.SEND_PHOTO_CONTEST}",
                callback_data=UserCallbacks.SEND_PHOTO
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text=f"{Emojis.INFO} {ButtonLabels.CONTEST_INACTIVE}",
                callback_data=UserCallbacks.NO_CONTEST
            )
        ])
    # Кнопка добавления трека всегда доступна
    buttons.append([
        InlineKeyboardButton(
            text=f"{Emojis.MUSIC} {ButtonLabels.ADD_TRACK}",
            callback_data=UserCallbacks.ADD_TRACK
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
