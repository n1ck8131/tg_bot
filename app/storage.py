"""
Хранилища данных в памяти.
В production рекомендуется использовать Redis или базу данных.
"""

import time
from dataclasses import dataclass, field
from typing import Optional

# Время жизни записей (в секундах)
POLLS_TTL = 86400  # 24 часа
FORWARDED_MESSAGES_TTL = 3600  # 1 час
PHOTO_CONTEST_TTL = 604800  # 7 дней


@dataclass
class PollData:
    """Данные опроса."""

    question: str
    options: list[str]
    votes: dict[str, list[int]] = field(default_factory=dict)
    allows_multiple: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass
class PhotoEntry:
    """Запись фото конкурса."""

    photo_id: str
    user_name: str
    created_at: float = field(default_factory=time.time)


@dataclass
class ForwardedMessage:
    """Данные пересланного сообщения."""

    message_id: int
    chat_id: int
    user_id: int
    user_name: str
    created_at: float = field(default_factory=time.time)


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

    def cleanup_old(self, ttl: int = POLLS_TTL) -> int:
        """Удаляет опросы старше TTL. Возвращает количество удаленных."""
        current_time = time.time()
        to_delete = [
            poll_id
            for poll_id, poll_data in self._polls.items()
            if current_time - poll_data.created_at > ttl
        ]
        for poll_id in to_delete:
            del self._polls[poll_id]
        return len(to_delete)


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

    def cleanup_old(self, ttl: int = FORWARDED_MESSAGES_TTL) -> int:
        """Удаляет сообщения старше TTL. Возвращает количество удаленных."""
        current_time = time.time()
        to_delete = [
            msg_id
            for msg_id, msg_data in self._messages.items()
            if current_time - msg_data.created_at > ttl
        ]
        for msg_id in to_delete:
            del self._messages[msg_id]
        return len(to_delete)


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


@dataclass
class Match:
    """Матч турнира."""

    match_id: str  # "R1M1", "R2M1", "FINAL"
    round_number: int  # 1, 2, 3...
    team1_name: str
    team2_name: str
    team1_members: list[str]
    team2_members: list[str]
    winner_team: Optional[int] = None  # 1 или 2
    status: str = "pending"  # pending, finished
    next_match_id: Optional[str] = None  # Куда идет победитель
    created_at: float = field(default_factory=time.time)


@dataclass
class Tournament:
    """Турнир бир-понга."""

    tournament_id: str
    all_participants: list[str]
    matches: dict[str, Match]  # match_id -> Match
    current_round: int = 1
    max_rounds: int = 1
    status: str = "in_progress"  # in_progress, finished
    winner_team: Optional[str] = None
    winner_members: Optional[list[str]] = None
    bracket_message_id: Optional[int] = None  # Для редактирования в группе
    created_at: float = field(default_factory=time.time)


class TournamentStorage:
    """Хранилище турнира."""

    def __init__(self) -> None:
        self._current: Optional[Tournament] = None

    def create_tournament(self, participants: list[str], matches: dict[str, Match]) -> Tournament:
        """Создает новый турнир с bracket."""
        # Находим максимальный номер раунда из всех матчей (самый надежный способ)
        max_rounds = max((m.round_number for m in matches.values()), default=1)

        tournament = Tournament(
            tournament_id=f"tournament_{int(time.time())}",
            all_participants=participants,
            matches=matches,
            current_round=1,
            max_rounds=max_rounds,
        )
        self._current = tournament
        return tournament

    def get_current(self) -> Optional[Tournament]:
        """Получить текущий турнир."""
        return self._current

    def set_match_winner(self, match_id: str, winner_team: int) -> None:
        """Установить победителя матча."""
        if not self._current or match_id not in self._current.matches:
            return

        match = self._current.matches[match_id]
        match.winner_team = winner_team
        match.status = "finished"

    def advance_winner(self, match_id: str) -> Optional[str]:
        """Продвинуть победителя в следующий раунд. Возвращает next_match_id."""
        if not self._current or match_id not in self._current.matches:
            return None

        match = self._current.matches[match_id]
        if not match.next_match_id or match.winner_team is None:
            return match.next_match_id

        next_match = self._current.matches.get(match.next_match_id)
        if not next_match:
            return None

        # Определяем победившую команду
        winner_name = match.team1_name if match.winner_team == 1 else match.team2_name
        winner_members = match.team1_members if match.winner_team == 1 else match.team2_members

        # Добавляем победителя в следующий матч
        if next_match.team1_name == "TBD":
            next_match.team1_name = winner_name
            next_match.team1_members = winner_members
        elif next_match.team2_name == "TBD":
            next_match.team2_name = winner_name
            next_match.team2_members = winner_members

        return match.next_match_id

    def check_round_complete(self) -> bool:
        """Проверить, завершен ли текущий раунд."""
        if not self._current:
            return False

        current_round_matches = [
            m
            for m in self._current.matches.values()
            if m.round_number == self._current.current_round
        ]

        return all(m.status == "finished" for m in current_round_matches)

    def advance_to_next_round(self) -> None:
        """Перейти к следующему раунду."""
        if self._current:
            self._current.current_round += 1

    def finish_tournament(self) -> None:
        """Завершить турнир и установить победителя."""
        if not self._current:
            return

        # Найти финальный матч
        final_matches = [
            m for m in self._current.matches.values() if m.round_number == self._current.max_rounds
        ]

        if final_matches and final_matches[0].status == "finished":
            final_match = final_matches[0]
            if final_match.winner_team == 1:
                self._current.winner_team = final_match.team1_name
                self._current.winner_members = final_match.team1_members
            else:
                self._current.winner_team = final_match.team2_name
                self._current.winner_members = final_match.team2_members

            self._current.status = "finished"

    def clear(self) -> None:
        """Очистить текущий турнир."""
        self._current = None


# Глобальные экземпляры хранилищ
polls_storage = PollsStorage()
photo_contest_storage = PhotoContestStorage()
forwarded_messages_storage = ForwardedMessagesStorage()
location_storage = LocationStorage()
tournament_storage = TournamentStorage()
