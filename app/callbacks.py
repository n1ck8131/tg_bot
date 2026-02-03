"""
Константы для callback_data.
Использование констант предотвращает опечатки и упрощает рефакторинг.
"""


class MenuCallbacks:
    """Callback'и главного меню."""

    PREFIX = "menu"
    BIRTHDAY = f"{PREFIX}:birthday"
    TRIP = f"{PREFIX}:trip"
    WISHLIST = f"{PREFIX}:wishlist"
    LOCATION = f"{PREFIX}:location"
    ASK = f"{PREFIX}:ask"
    PLAYLIST = f"{PREFIX}:playlist"
    HELP = f"{PREFIX}:help"


class AdminCallbacks:
    """Callback'и админского меню."""

    PREFIX = "admin"
    SET_LOCATION = f"{PREFIX}:setlocation"
    PHOTO_START = f"{PREFIX}:photo_start"
    PHOTO_STOP = f"{PREFIX}:photo_stop"
    SEND_PHOTO = f"{PREFIX}:send_photo"
    ADD_TRACK = f"{PREFIX}:add_track"
    SPY = f"{PREFIX}:spy"
    POLL_SINGLE = f"{PREFIX}:poll_single"
    POLL_MULTIPLE = f"{PREFIX}:poll_multiple"
    POLL_RESULTS = f"{PREFIX}:poll_results"
    BROADCAST = f"{PREFIX}:broadcast"
    TOURNAMENT = f"{PREFIX}:tournament"


class UserCallbacks:
    """Callback'и пользовательского меню."""

    PREFIX = "user"
    SEND_PHOTO = f"{PREFIX}:send_photo"
    NO_CONTEST = f"{PREFIX}:no_contest"
    ADD_TRACK = f"{PREFIX}:add_track"


class TournamentCallbacks:
    """Callback'и турнирной системы."""

    PREFIX = "tournament"
    START = f"{PREFIX}:start"
    VIEW_BRACKET = f"{PREFIX}:view"
    SELECT_MATCH = f"{PREFIX}:match"  # tournament:match:R1M1
    WINNER_TEAM1 = f"{PREFIX}:win1"  # tournament:win1:R1M1
    WINNER_TEAM2 = f"{PREFIX}:win2"  # tournament:win2:R1M1
    NEXT_ROUND = f"{PREFIX}:next_round"
    FINISH = f"{PREFIX}:finish"
    CANCEL = f"{PREFIX}:cancel"


class AssassinCallbacks:
    """Callback'и игры Assassin."""

    PREFIX = "assassin"

    # Админ
    OPEN_REGISTRATION = f"{PREFIX}:open_reg"
    SET_WEAPONS = f"{PREFIX}:set_weapons"
    SET_LOCATIONS = f"{PREFIX}:set_locations"
    SHOW_LISTS = f"{PREFIX}:show_lists"
    START_GAME = f"{PREFIX}:start_game"
    RESET_GAME = f"{PREFIX}:reset"
    TEST_MODE = f"{PREFIX}:test_mode"
    ADMIN_MENU = f"{PREFIX}:admin_menu"

    # Игрок
    REGISTER = f"{PREFIX}:register"
    SHOW_CONTRACT = f"{PREFIX}:show_contract"
    I_AM_DEAD = f"{PREFIX}:i_am_dead"
    CONFIRM_DEATH = f"{PREFIX}:confirm_death"
    CANCEL_DEATH = f"{PREFIX}:cancel_death"

    # Тестовый режим
    TEST_PLAYERS_LIST = f"{PREFIX}:test_list"
    TEST_SELECT_PLAYER = f"{PREFIX}:test_player"  # assassin:test_player:123
    TEST_KILL_PLAYER = f"{PREFIX}:test_kill"  # assassin:test_kill:123
    TEST_CONFIRM_KILL = f"{PREFIX}:test_confirm"  # assassin:test_confirm:123
    TEST_CANCEL = f"{PREFIX}:test_cancel"
