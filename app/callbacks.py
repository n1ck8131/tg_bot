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
    BEERPONG = f"{PREFIX}:beerpong"
    SPY = f"{PREFIX}:spy"
    POLL = f"{PREFIX}:poll"
    POLL_RESULTS = f"{PREFIX}:poll_results"
    BROADCAST = f"{PREFIX}:broadcast"


class UserCallbacks:
    """Callback'и пользовательского меню."""

    PREFIX = "user"
    SEND_PHOTO = f"{PREFIX}:send_photo"
    NO_CONTEST = f"{PREFIX}:no_contest"
    ADD_TRACK = f"{PREFIX}:add_track"
