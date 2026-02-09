"""
Клавиатуры бота.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from app.callbacks import MenuCallbacks, AdminCallbacks, UserCallbacks, TournamentCallbacks, AssassinCallbacks, PhotoVoteCallbacks
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
                KeyboardButton(text=f"🔪 Достать ножи"),
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
                text=f"🗳 {ButtonLabels.PHOTO_START_VOTING}",
                callback_data=AdminCallbacks.PHOTO_START_VOTING
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🏁 {ButtonLabels.PHOTO_END_VOTING}",
                callback_data=AdminCallbacks.PHOTO_END_VOTING
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
                text="🔪 Достать ножи",
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


# === Assassin Game Keyboards ===


def get_assassin_admin_menu(show_register: bool = False, admin_registered: bool = False) -> InlineKeyboardMarkup:
    """Админ-меню для игры Assassin."""
    buttons = [
        [
            InlineKeyboardButton(
                text=f"✅ {ButtonLabels.ASSASSIN_OPEN_REG}",
                callback_data=AssassinCallbacks.OPEN_REGISTRATION
            ),
        ],
    ]

    # Кнопка регистрации для админа (только если регистрация открыта)
    if show_register and not admin_registered:
        buttons.append([
            InlineKeyboardButton(
                text=f"👤 Зарегистрироваться как игрок",
                callback_data=AssassinCallbacks.REGISTER
            ),
        ])

    # Кнопка "Ты зарегистрирован" убрана - она бесполезна во время регистрации
    # Контракт будет доступен только после старта игры через личные сообщения

    buttons.extend([
        [
            InlineKeyboardButton(
                text=f"🗡 {ButtonLabels.ASSASSIN_SET_WEAPONS}",
                callback_data=AssassinCallbacks.SET_WEAPONS
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"📍 {ButtonLabels.ASSASSIN_SET_LOCATIONS}",
                callback_data=AssassinCallbacks.SET_LOCATIONS
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"📋 {ButtonLabels.ASSASSIN_SHOW_LISTS}",
                callback_data=AssassinCallbacks.SHOW_LISTS
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🎮 {ButtonLabels.ASSASSIN_START_GAME}",
                callback_data=AssassinCallbacks.START_GAME
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🔄 {ButtonLabels.ASSASSIN_RESET}",
                callback_data=AssassinCallbacks.RESET_GAME
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🧪 {ButtonLabels.ASSASSIN_TEST_MODE}",
                callback_data=AssassinCallbacks.TEST_MODE
            ),
        ],
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_assassin_registration_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура регистрации для игрока."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"✅ {ButtonLabels.ASSASSIN_REGISTER}",
                callback_data=AssassinCallbacks.REGISTER
            ),
        ],
    ])


def get_assassin_player_menu() -> InlineKeyboardMarkup:
    """Меню игрока во время игры."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"☠️ {ButtonLabels.ASSASSIN_I_AM_DEAD}",
                callback_data=AssassinCallbacks.I_AM_DEAD
            ),
        ],
    ])


def get_assassin_death_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения смерти."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=ButtonLabels.ASSASSIN_CONFIRM_DEATH,
                callback_data=AssassinCallbacks.CONFIRM_DEATH
            ),
        ],
        [
            InlineKeyboardButton(
                text=ButtonLabels.ASSASSIN_CANCEL_DEATH,
                callback_data=AssassinCallbacks.CANCEL_DEATH
            ),
        ],
    ])


def get_assassin_test_count_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора количества виртуальных игроков."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=ButtonLabels.ASSASSIN_TEST_DEFAULT,
                callback_data=f"{AssassinCallbacks.TEST_MODE}:22"
            ),
        ],
    ])


def get_assassin_test_menu() -> InlineKeyboardMarkup:
    """Меню тестового режима."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"👥 {ButtonLabels.ASSASSIN_TEST_PLAYERS_LIST}",
                callback_data=AssassinCallbacks.TEST_PLAYERS_LIST
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🎮 {ButtonLabels.ASSASSIN_START_GAME}",
                callback_data=AssassinCallbacks.START_GAME
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"◀️ {ButtonLabels.ASSASSIN_ADMIN_MENU}",
                callback_data=AssassinCallbacks.ADMIN_MENU
            ),
        ],
    ])


def get_assassin_test_player_list_keyboard(players: list) -> InlineKeyboardMarkup:
    """Клавиатура списка виртуальных игроков."""
    buttons = []
    for player in players:
        status = "✅" if player["is_alive"] else "☠️"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {player['display_name']}",
                callback_data=f"{AssassinCallbacks.TEST_SELECT_PLAYER}:{player['id']}"
            ),
        ])
    buttons.append([
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=AssassinCallbacks.ADMIN_MENU
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_assassin_test_player_actions_keyboard(player_id: int, is_alive: bool) -> InlineKeyboardMarkup:
    """Клавиатура действий с виртуальным игроком."""
    buttons = []
    if is_alive:
        buttons.append([
            InlineKeyboardButton(
                text="☠️ Симулировать 'Я мёртв'",
                callback_data=f"{AssassinCallbacks.TEST_KILL_PLAYER}:{player_id}"
            ),
        ])
    buttons.append([
        InlineKeyboardButton(
            text="◀️ К списку",
            callback_data=AssassinCallbacks.TEST_PLAYERS_LIST
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_assassin_test_death_confirm_keyboard(player_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения смерти виртуального игрока."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=ButtonLabels.ASSASSIN_CONFIRM_DEATH,
                callback_data=f"{AssassinCallbacks.TEST_CONFIRM_KILL}:{player_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=ButtonLabels.ASSASSIN_CANCEL_DEATH,
                callback_data=f"{AssassinCallbacks.TEST_SELECT_PLAYER}:{player_id}"
            ),
        ],
    ])


# === Photo Contest Keyboards ===


def get_photo_voting_keyboard(entries: list[tuple[int, 'PhotoEntry']]) -> InlineKeyboardMarkup:
    """Клавиатура для голосования за фото.

    Args:
        entries: Список кортежей (user_id, PhotoEntry)
    """
    from app.messages import Messages

    buttons = []
    for num, (user_id, entry) in enumerate(entries, 1):
        button_text = Messages.PHOTO_BUTTON_VOTE.format(num=num, user=entry.user_name)
        buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"{PhotoVoteCallbacks.PREFIX}:{user_id}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
