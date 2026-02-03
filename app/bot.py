"""
Точка входа приложения.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeAllPrivateChats, Update, ErrorEvent

from app.config import settings
from app.handlers import get_all_routers
from app.middleware import RateLimitMiddleware
from app.database import init_database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """Настройка меню команд."""
    # Команды для группы
    group_commands = [
        BotCommand(command="start", description="Главное меню"),
    ]

    await bot.set_my_commands(
        commands=group_commands,
        scope=BotCommandScopeChat(chat_id=settings.bot.group_id)
    )

    # Команды для личных чатов
    private_commands = [
        BotCommand(command="start", description="Главное меню"),
    ]

    await bot.set_my_commands(
        commands=private_commands,
        scope=BotCommandScopeAllPrivateChats()
    )

    # Команды для админа в личке
    admin_commands = [
        BotCommand(command="start", description="Главное меню"),
    ]

    await bot.set_my_commands(
        commands=admin_commands,
        scope=BotCommandScopeChat(chat_id=settings.bot.admin_id)
    )

    logger.info("Меню команд установлено")


async def handle_errors(event: ErrorEvent) -> None:
    """Глобальный обработчик ошибок."""
    logger.exception(
        f"Произошла ошибка при обработке обновления {event.update.update_id}: {event.exception}",
        exc_info=event.exception
    )


async def main() -> None:
    """Главная функция запуска бота."""
    # Инициализируем базу данных
    init_database()

    bot = Bot(token=settings.bot.token)
    dp = Dispatcher()

    # Регистрируем middleware для rate limiting
    dp.message.middleware(RateLimitMiddleware(rate_limit=10, time_window=30))
    dp.callback_query.middleware(RateLimitMiddleware(rate_limit=20, time_window=30))

    # Регистрируем глобальный обработчик ошибок
    dp.errors.register(handle_errors)

    # Регистрируем все роутеры
    for router in get_all_routers():
        dp.include_router(router)

    await setup_bot_commands(bot)

    logger.info("Бот запущен")
    logger.info(f"Admin ID: {settings.bot.admin_id}")
    logger.info(f"Group ID: {settings.bot.group_id}")

    # Используем async with для graceful shutdown
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
