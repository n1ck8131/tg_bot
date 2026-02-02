"""
FSM состояния для бота.
"""

from aiogram.fsm.state import State, StatesGroup


class AskState(StatesGroup):
    """Состояние отправки сообщения организатору."""

    waiting_for_question = State()


class PhotoContestState(StatesGroup):
    """Состояние конкурса фото."""

    waiting_for_photo = State()


class GeoState(StatesGroup):
    """Состояние установки геопозиции."""

    waiting_for_location = State()


class AdminBroadcastState(StatesGroup):
    """Состояние отправки broadcast сообщения."""

    waiting_for_text = State()


class AdminPollState(StatesGroup):
    """Состояние создания опроса."""

    waiting_for_poll_single = State()
    waiting_for_poll_multiple = State()


class AddTrackState(StatesGroup):
    """Состояние добавления трека в плейлист."""

    waiting_for_link = State()


class TournamentState(StatesGroup):
    """Состояние турнирной системы бир-понга."""

    waiting_for_participants = State()
    selecting_match_winner = State()
