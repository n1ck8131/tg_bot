"""Helper функции для работы с игрой "Достать ножи"."""
from typing import Optional

from app.database import get_active_game, get_player_by_tg_id
from app.messages import Messages


def get_game_state() -> tuple[Optional[dict], bool, bool]:
    """
    Получить состояние игры.

    Returns:
        (game, show_register, admin_registered)
    """
    from app.config import settings
    ADMIN_ID = settings.bot.admin_id

    game = get_active_game()
    show_register = game and game["status"] == "registration"
    admin_registered = False
    if game:
        admin_registered = get_player_by_tg_id(game["id"], ADMIN_ID) is not None
    return game, show_register, admin_registered


def check_active_game() -> tuple[bool, Optional[dict], str]:
    """
    Проверить активную игру.

    Returns:
        (is_valid, game, error_message)
    """
    game = get_active_game()
    if not game:
        return False, None, Messages.ASSASSIN_NO_ACTIVE_GAME
    if game["status"] != "running":
        return False, game, Messages.ASSASSIN_GAME_NOT_RUNNING
    return True, game, ""


def get_player_with_validation(
    game_id: int, tg_user_id: int
) -> tuple[bool, Optional[dict], str]:
    """
    Получить игрока с валидацией.

    Returns:
        (is_valid, player, error_message)
    """
    player = get_player_by_tg_id(game_id, tg_user_id)
    if not player:
        return False, None, Messages.ASSASSIN_NOT_IN_GAME
    if not player["is_alive"]:
        return False, player, Messages.ASSASSIN_ALREADY_DEAD
    return True, player, ""
