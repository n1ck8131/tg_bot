"""
Клавиатуры бота.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from app.callbacks import MenuCallbacks, AdminCallbacks, UserCallbacks, TournamentCallbacks
from app.messages import ButtonLabels, Emojis
from app.storage import photo_contest_storage, Match, Tournament
from app.tournament_utils import get_pending_matches


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
                KeyboardButton(text=f"{Emojis.TOURNAMENT} Турнир"),
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
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{Emojis.PHOTO} {ButtonLabels.PHOTO_START}",
                callback_data=AdminCallbacks.PHOTO_START
            ),
        ],
        [
            InlineKeyboardButton(
                text="🛑 {0}".format(ButtonLabels.PHOTO_STOP),
                callback_data=AdminCallbacks.PHOTO_STOP
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.TOURNAMENT} {ButtonLabels.TOURNAMENT}",
                callback_data=AdminCallbacks.TOURNAMENT
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.LOCATION} {ButtonLabels.SET_LOCATION}",
                callback_data=AdminCallbacks.SET_LOCATION
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.SPY} {ButtonLabels.SPY}",
                callback_data=AdminCallbacks.SPY
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.POLL} {ButtonLabels.CREATE_POLL_SINGLE}",
                callback_data=AdminCallbacks.POLL_SINGLE
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.POLL} {ButtonLabels.CREATE_POLL_MULTIPLE}",
                callback_data=AdminCallbacks.POLL_MULTIPLE
            ),
        ],
        [
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
        [
            InlineKeyboardButton(
                text=f"{Emojis.MUSIC} {ButtonLabels.ADD_TRACK}",
                callback_data=AdminCallbacks.ADD_TRACK
            ),
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


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
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{Emojis.MUSIC} {ButtonLabels.ADD_TRACK}",
                callback_data=UserCallbacks.ADD_TRACK
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{Emojis.PHOTO} {ButtonLabels.SEND_PHOTO_CONTEST}",
                callback_data=UserCallbacks.SEND_PHOTO
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tournament_match_selection_keyboard(tournament: Tournament) -> InlineKeyboardMarkup:
    """Клавиатура для выбора матча для ввода результата."""
    pending_matches = get_pending_matches(tournament)

    buttons = []
    for match in pending_matches:
        button_text = f"{match.match_id}: {match.team1_name} vs {match.team2_name}"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"{TournamentCallbacks.SELECT_MATCH}:{match.match_id}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="❌ Отмена", callback_data=TournamentCallbacks.CANCEL
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_match_winner_keyboard(match: Match) -> InlineKeyboardMarkup:
    """Клавиатура для выбора победителя матча."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🔴 {match.team1_name}",
                    callback_data=f"{TournamentCallbacks.WINNER_TEAM1}:{match.match_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🔵 {match.team2_name}",
                    callback_data=f"{TournamentCallbacks.WINNER_TEAM2}:{match.match_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад", callback_data=TournamentCallbacks.VIEW_BRACKET
                )
            ],
        ]
    )


def get_tournament_control_keyboard(tournament: Tournament) -> InlineKeyboardMarkup:
    """Клавиатура управления турниром."""
    from app.storage import tournament_storage

    buttons = []

    # Кнопка ввода результатов (если есть незавершенные матчи)
    pending = get_pending_matches(tournament)
    if pending:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📝 Ввести результат ({len(pending)} матчей)",
                    callback_data=TournamentCallbacks.SELECT_MATCH,
                )
            ]
        )

    # Кнопка перехода к следующему раунду (если текущий завершен)
    if (
        tournament_storage.check_round_complete()
        and tournament.current_round < tournament.max_rounds
    ):
        buttons.append(
            [
                InlineKeyboardButton(
                    text="▶️ Следующий раунд",
                    callback_data=TournamentCallbacks.NEXT_ROUND,
                )
            ]
        )

    # Кнопка завершения турнира (если финал завершен)
    final_match = [
        m for m in tournament.matches.values() if m.round_number == tournament.max_rounds
    ]
    if final_match and final_match[0].status == "finished":
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🏆 Завершить турнир",
                    callback_data=TournamentCallbacks.FINISH,
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔄 Обновить сетку", callback_data=TournamentCallbacks.VIEW_BRACKET
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
