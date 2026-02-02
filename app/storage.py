"""
Хранилища данных в памяти.
В production рекомендуется использовать Redis или базу данных.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PollData:
    """Данные опроса."""

    question: str
    options: list[str]
    votes: dict[str, list[int]] = field(default_factory=dict)
    allows_multiple: bool = False


@dataclass
class PhotoEntry:
    """Запись фото конкурса."""

    photo_id: str
    user_name: str


@dataclass
class ForwardedMessage:
    """Данные пересланного сообщения."""

    message_id: int
    chat_id: int
    user_id: int
    user_name: str


@dataclass
class LocationData:
    """Данные геопозиции."""

    latitude: float
    longitude: float
    address: str = ""


class PollsStorage:
    """Хранилище опросов."""

    def __init__(self) -> None:
        self._polls: dict[str, PollData] = {}

    def add(self, poll_id: str, data: PollData) -> None:
        self._polls[poll_id] = data

    def get(self, poll_id: str) -> Optional[PollData]:
        return self._polls.get(poll_id)

    def exists(self, poll_id: str) -> bool:
        return poll_id in self._polls

    def update_vote(self, poll_id: str, user_name: str, option_ids: list[int]) -> None:
        if poll_id in self._polls:
            if option_ids:
                self._polls[poll_id].votes[user_name] = option_ids
            else:
                self._polls[poll_id].votes.pop(user_name, None)

    def get_all(self) -> dict[str, PollData]:
        return self._polls.copy()

    def is_empty(self) -> bool:
        return len(self._polls) == 0


class PhotoContestStorage:
    """Хранилище конкурса фото."""

    def __init__(self) -> None:
        self._active: bool = False
        self._entries: dict[int, PhotoEntry] = {}

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self) -> None:
        self._active = True
        self._entries.clear()

    def stop(self) -> None:
        self._active = False

    def add_entry(self, user_id: int, entry: PhotoEntry) -> None:
        self._entries[user_id] = entry

    def has_entry(self, user_id: int) -> bool:
        return user_id in self._entries

    def get_entries(self) -> list[tuple[int, PhotoEntry]]:
        return list(self._entries.items())

    def entries_count(self) -> int:
        return len(self._entries)

    def is_empty(self) -> bool:
        return len(self._entries) == 0


class ForwardedMessagesStorage:
    """Хранилище пересланных сообщений."""

    def __init__(self) -> None:
        self._messages: dict[int, ForwardedMessage] = {}

    def add(self, message_id: int, data: ForwardedMessage) -> None:
        self._messages[message_id] = data

    def get(self, message_id: int) -> Optional[ForwardedMessage]:
        return self._messages.get(message_id)

    def exists(self, message_id: int) -> bool:
        return message_id in self._messages


class LocationStorage:
    """Хранилище геопозиции."""

    def __init__(self) -> None:
        self._data: Optional[LocationData] = None

    def set(self, data: LocationData) -> None:
        self._data = data

    def get(self) -> Optional[LocationData]:
        return self._data

    def set_address(self, address: str) -> None:
        if self._data:
            self._data.address = address

    def is_set(self) -> bool:
        return self._data is not None


# Глобальные экземпляры хранилищ
polls_storage = PollsStorage()
photo_contest_storage = PhotoContestStorage()
forwarded_messages_storage = ForwardedMessagesStorage()
location_storage = LocationStorage()
