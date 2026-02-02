"""
Точка входа приложения.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeAllPrivateChats

from app.config import settings
from app.handlers import get_all_routers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """Настройка меню команд."""
    # Команды для группы
    group_commands = [
        BotCommand(command="menu", description="Главное меню с кнопками"),
        BotCommand(command="birthday", description="Информация о дне рождения"),
        BotCommand(command="trip", description="Информация о выезде"),
        BotCommand(command="wishlist", description="Ссылка на вишлист"),
        BotCommand(command="location", description="Геопозиция места"),
        BotCommand(command="ask", description="Написать сообщение Севе"),
        BotCommand(command="help", description="Список команд"),
    ]

    await bot.set_my_commands(
        commands=group_commands,
        scope=BotCommandScopeChat(chat_id=settings.bot.group_id)
    )

    # Команды для личных чатов
    private_commands = [
        BotCommand(command="start", description="Открыть меню"),
    ]

    await bot.set_my_commands(
        commands=private_commands,
        scope=BotCommandScopeAllPrivateChats()
    )

    # Команды для админа в личке
    admin_commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="photo_start", description="Начать конкурс фото"),
        BotCommand(command="photo_stop", description="Завершить конкурс фото"),
        BotCommand(command="beerpong", description="Бир-понг"),
        BotCommand(command="spy", description="Игра в шпиона"),
        BotCommand(command="setlocation", description="Установить геопозицию"),
        BotCommand(command="broadcast", description="Сообщение в группу"),
    ]

    await bot.set_my_commands(
        commands=admin_commands,
        scope=BotCommandScopeChat(chat_id=settings.bot.admin_id)
    )

    logger.info("Меню команд установлено")


async def main() -> None:
    """Главная функция запуска бота."""
    bot = Bot(token=settings.bot.token)
    dp = Dispatcher()

    # Регистрируем все роутеры
    for router in get_all_routers():
        dp.include_router(router)

    await setup_bot_commands(bot)

    logger.info("Бот запущен")
    logger.info(f"Admin ID: {settings.bot.admin_id}")
    logger.info(f"Group ID: {settings.bot.group_id}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
