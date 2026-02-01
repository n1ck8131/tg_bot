import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n"
        "Я бот с командами. Используй /help для списка команд."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
Доступные команды:
/start - Начать работу с ботом
/help - Показать это сообщение
/info - Информация о боте
/echo <текст> - Повторить ваше сообщение
"""
    await message.answer(help_text)


@router.message(Command("info"))
async def cmd_info(message: Message):
    await message.answer(
        "Это тестовый Telegram бот.\n"
        "Создан с использованием aiogram 3.x"
    )


@router.message(Command("echo"))
async def cmd_echo(message: Message):
    text = message.text.replace("/echo", "").strip()
    if text:
        await message.answer(text)
    else:
        await message.answer("Использование: /echo <текст>")


@router.message()
async def handle_message(message: Message):
    await message.answer("Я не понимаю это сообщение. Используй /help для списка команд.")


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
