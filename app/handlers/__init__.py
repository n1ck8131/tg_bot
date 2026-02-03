"""
Обработчики бота.
"""

from aiogram import Router

from app.handlers.group import group_router
from app.handlers.admin import admin_router
from app.handlers.user import user_router
from app.handlers.tournament import tournament_router
from app.handlers.spy_game import assassin_router


def get_all_routers() -> list[Router]:
    """Возвращает все роутеры в правильном порядке.

    Порядок важен:
    1. admin_router - команды админа в private чате
    2. user_router - команды пользователей в private чате
    3. assassin_router, tournament_router - callback handlers
    4. group_router - команды в групповом чате
    """
    return [admin_router, user_router, assassin_router, tournament_router, group_router]
