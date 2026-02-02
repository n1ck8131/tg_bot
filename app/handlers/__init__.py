"""
Обработчики бота.
"""

from aiogram import Router

from app.handlers.group import group_router
from app.handlers.admin import admin_router
from app.handlers.user import user_router


def get_all_routers() -> list[Router]:
    """Возвращает все роутеры в правильном порядке."""
    return [admin_router, user_router, group_router]
