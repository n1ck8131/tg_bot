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
