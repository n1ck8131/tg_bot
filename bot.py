import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, PollAnswer, BotCommand, BotCommandScopeChat,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, ADMIN_ID, GROUP_ID, BIRTHDAY_INFO, TRIP_INFO, WISHLIST_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния
class AskState(StatesGroup):
    waiting_for_question = State()


# Роутеры
admin_router = Router()
group_router = Router()

# Хранение данных опросов: poll_id -> {question, options, votes, allows_multiple}
polls_storage: dict[str, dict] = {}

# Маппинг: message_id пересланного сообщения -> оригинальное сообщение в группе
forwarded_messages: dict[int, dict] = {}


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню с inline-кнопками"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎂 День рождения", callback_data="menu:birthday"),
            InlineKeyboardButton(text="🚗 Выезд", callback_data="menu:trip"),
        ],
        [
            InlineKeyboardButton(text="🎁 Вишлист", callback_data="menu:wishlist"),
            InlineKeyboardButton(text="❓ Задать вопрос", callback_data="menu:ask"),
        ],
        [
            InlineKeyboardButton(text="📋 Помощь", callback_data="menu:help"),
        ],
    ])


# === Фильтры ===

def is_admin(message: Message) -> bool:
    return message.from_user.id == ADMIN_ID


def is_group_chat(message: Message) -> bool:
    return message.chat.id == GROUP_ID


def is_private_chat(message: Message) -> bool:
    return message.chat.type == ChatType.PRIVATE


# === Команды для группы ===

@group_router.message(Command("birthday"), F.chat.id == GROUP_ID)
async def cmd_birthday(message: Message):
    info = BIRTHDAY_INFO.replace("\\n", "\n")
    await message.answer(f"🎂 *День рождения*\n\n{info}", parse_mode="Markdown")


@group_router.message(Command("trip"), F.chat.id == GROUP_ID)
async def cmd_trip(message: Message):
    info = TRIP_INFO.replace("\\n", "\n")
    await message.answer(f"🚗 *Информация о выезде*\n\n{info}", parse_mode="Markdown")


@group_router.message(Command("wishlist"), F.chat.id == GROUP_ID)
async def cmd_wishlist(message: Message):
    await message.answer(f"🎁 *Вишлист*\n\n{WISHLIST_URL}", parse_mode="Markdown")


@group_router.message(Command("help"), F.chat.id == GROUP_ID)
async def cmd_help_group(message: Message):
    help_text = """
*Доступные команды:*

/birthday — информация о дне рождения
/trip — информация о выезде
/wishlist — ссылка на вишлист
/ask — задать вопрос организатору
/help — показать это сообщение

Или используй кнопки в /start
"""
    await message.answer(help_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())


# === Callback-обработчики для inline-кнопок ===

@group_router.callback_query(F.data == "menu:birthday")
async def callback_birthday(callback: CallbackQuery):
    info = BIRTHDAY_INFO.replace("\\n", "\n")
    await callback.message.answer(f"🎂 *День рождения*\n\n{info}", parse_mode="Markdown")
    await callback.answer()


@group_router.callback_query(F.data == "menu:trip")
async def callback_trip(callback: CallbackQuery):
    info = TRIP_INFO.replace("\\n", "\n")
    await callback.message.answer(f"🚗 *Информация о выезде*\n\n{info}", parse_mode="Markdown")
    await callback.answer()


@group_router.callback_query(F.data == "menu:wishlist")
async def callback_wishlist(callback: CallbackQuery):
    await callback.message.answer(f"🎁 *Вишлист*\n\n{WISHLIST_URL}", parse_mode="Markdown")
    await callback.answer()


@group_router.callback_query(F.data == "menu:ask")
async def callback_ask(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AskState.waiting_for_question)
    await callback.message.answer("✏️ Напишите ваш вопрос:")
    await callback.answer()


@group_router.callback_query(F.data == "menu:help")
async def callback_help(callback: CallbackQuery):
    help_text = """
*Доступные команды:*

/birthday — информация о дне рождения
/trip — информация о выезде
/wishlist — ссылка на вишлист
/ask — задать вопрос организатору
/help — показать это сообщение
"""
    await callback.message.answer(help_text, parse_mode="Markdown")
    await callback.answer()


@group_router.message(CommandStart(), F.chat.id == GROUP_ID)
async def cmd_start_group(message: Message):
    await message.answer(
        "👋 Привет! Я бот для организации дня рождения.\n\n"
        "Выбери, что тебя интересует:",
        reply_markup=get_main_menu_keyboard()
    )


@group_router.message(Command("menu"), F.chat.id == GROUP_ID)
async def cmd_menu(message: Message):
    await message.answer(
        "📋 Главное меню:",
        reply_markup=get_main_menu_keyboard()
    )


# === Команды для админа (личка) ===

@admin_router.message(CommandStart(), F.chat.type == ChatType.PRIVATE, F.from_user.id == ADMIN_ID)
async def cmd_start_admin(message: Message):
    await message.answer(
        "Привет, админ! Доступные команды:\n\n"
        "/poll Вопрос | Вариант 1 | Вариант 2 | ... — опрос (один ответ)\n"
        "/pollm Вопрос | Вариант 1 | Вариант 2 | ... — опрос (несколько ответов)\n"
        "/poll_results — результаты всех опросов\n"
        "/broadcast <текст> — отправить сообщение в группу\n\n"
        "Чтобы ответить на вопрос из группы, просто ответь на пересланное сообщение."
    )


async def create_poll(message: Message, bot: Bot, allows_multiple: bool):
    """Создание опроса с возможностью выбора одного или нескольких ответов"""
    command = "/pollm" if allows_multiple else "/poll"
    text = message.text.replace(command, "").strip()

    if not text or "|" not in text:
        await message.answer(f"Формат: {command} Вопрос | Вариант 1 | Вариант 2 | ...")
        return

    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        await message.answer("Нужен вопрос и минимум 2 варианта ответа")
        return

    question = parts[0]
    options = parts[1:]

    if len(options) > 10:
        await message.answer("Максимум 10 вариантов ответа")
        return

    try:
        poll_message = await bot.send_poll(
            chat_id=GROUP_ID,
            question=question,
            options=options,
            is_anonymous=False,
            allows_multiple_answers=allows_multiple
        )

        polls_storage[poll_message.poll.id] = {
            "question": question,
            "options": options,
            "votes": {},
            "allows_multiple": allows_multiple
        }

        mode = "несколько ответов" if allows_multiple else "один ответ"
        await message.answer(f"Опрос создан в группе! ({mode})")
    except Exception as e:
        await message.answer(f"Ошибка при создании опроса: {e}")


@admin_router.message(Command("poll"), F.chat.type == ChatType.PRIVATE, F.from_user.id == ADMIN_ID)
async def cmd_poll(message: Message, bot: Bot):
    await create_poll(message, bot, allows_multiple=False)


@admin_router.message(Command("pollm"), F.chat.type == ChatType.PRIVATE, F.from_user.id == ADMIN_ID)
async def cmd_poll_multi(message: Message, bot: Bot):
    await create_poll(message, bot, allows_multiple=True)


@admin_router.message(Command("poll_results"), F.chat.type == ChatType.PRIVATE, F.from_user.id == ADMIN_ID)
async def cmd_poll_results(message: Message, bot: Bot):
    if not polls_storage:
        await message.answer("Нет опросов")
        return

    results = "📊 *Результаты всех опросов:*\n\n"

    for poll_id, poll_data in polls_storage.items():
        question = poll_data["question"]
        options = poll_data["options"]
        votes = poll_data["votes"]
        mode = "несколько" if poll_data["allows_multiple"] else "один"

        results += f"❓ *{question}* ({mode})\n"

        vote_counts: dict[int, list[str]] = {}
        for user, option_ids in votes.items():
            for opt_id in option_ids:
                if opt_id not in vote_counts:
                    vote_counts[opt_id] = []
                vote_counts[opt_id].append(user)

        for i, option in enumerate(options):
            users = vote_counts.get(i, [])
            count = len(users)
            results += f"  • {option}: {count} голос(ов)\n"
            for user in users:
                results += f"      - {user}\n"

        if not votes:
            results += "  _Пока никто не голосовал_\n"

        results += "\n"

    await message.answer(results, parse_mode="Markdown")


@admin_router.message(Command("broadcast"), F.chat.type == ChatType.PRIVATE, F.from_user.id == ADMIN_ID)
async def cmd_broadcast(message: Message, bot: Bot):
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("Формат: /broadcast <текст>")
        return

    try:
        await bot.send_message(GROUP_ID, f"📢 {text}")
        await message.answer("Сообщение отправлено в группу!")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


# === Обработка ответов админа на пересланные сообщения ===

@admin_router.message(F.chat.type == ChatType.PRIVATE, F.from_user.id == ADMIN_ID, F.reply_to_message)
async def handle_admin_reply(message: Message, bot: Bot):
    reply_to = message.reply_to_message

    if reply_to.message_id not in forwarded_messages:
        return

    original = forwarded_messages[reply_to.message_id]

    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            text=f"💬 {message.text}",
            reply_to_message_id=original["message_id"]
        )
        await message.answer("Ответ отправлен в группу!")
    except Exception as e:
        await message.answer(f"Ошибка при отправке: {e}")


# === Команда для вопросов организатору ===

@group_router.message(Command("ask"), F.chat.id == GROUP_ID)
async def cmd_ask(message: Message, state: FSMContext):
    await state.set_state(AskState.waiting_for_question)
    await message.reply("Напишите ваш вопрос:")


@group_router.message(AskState.waiting_for_question, F.chat.id == GROUP_ID)
async def process_question(message: Message, bot: Bot, state: FSMContext):
    await state.clear()

    text = message.text
    if not text:
        return

    user = message.from_user
    user_display = user.full_name
    if user.username:
        user_display += f" (@{user.username})"

    forward_text = (
        f"📨 *Вопрос из группы*\n\n"
        f"*От:* {user_display}\n"
        f"*Вопрос:* {text}\n\n"
        f"_Ответь на это сообщение, чтобы ответить в группу_"
    )

    try:
        sent = await bot.send_message(ADMIN_ID, forward_text, parse_mode="Markdown")
        forwarded_messages[sent.message_id] = {
            "message_id": message.message_id,
            "chat_id": message.chat.id,
            "user_id": user.id,
            "user_name": user_display
        }
    except Exception as e:
        logger.error(f"Ошибка при пересылке админу: {e}")


# === Обработка голосов в опросах ===

@admin_router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    poll_id = poll_answer.poll_id

    if poll_id not in polls_storage:
        return

    user = poll_answer.user
    user_name = user.full_name
    if user.username:
        user_name = f"@{user.username}"

    if poll_answer.option_ids:
        polls_storage[poll_id]["votes"][user_name] = poll_answer.option_ids
    else:
        # Пользователь отменил голос
        polls_storage[poll_id]["votes"].pop(user_name, None)


# === Обработка остальных личных сообщений ===

@admin_router.message(F.chat.type == ChatType.PRIVATE)
async def handle_private_other(message: Message):
    if message.from_user.id == ADMIN_ID:
        return

    await message.answer(
        "Этот бот предназначен для группового чата.\n"
        "Если вы хотите связаться с организатором, напишите в группу и упомяните бота."
    )


async def setup_bot_commands(bot: Bot):
    """Настройка меню команд для группы"""
    group_commands = [
        BotCommand(command="menu", description="Главное меню с кнопками"),
        BotCommand(command="birthday", description="Информация о дне рождения"),
        BotCommand(command="trip", description="Информация о выезде"),
        BotCommand(command="wishlist", description="Ссылка на вишлист"),
        BotCommand(command="ask", description="Задать вопрос организатору"),
        BotCommand(command="help", description="Список команд"),
    ]

    await bot.set_my_commands(
        commands=group_commands,
        scope=BotCommandScopeChat(chat_id=GROUP_ID)
    )
    logger.info("Меню команд установлено для группы")


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(admin_router)
    dp.include_router(group_router)

    await setup_bot_commands(bot)

    logger.info("Бот запущен")
    logger.info(f"Admin ID: {ADMIN_ID}")
    logger.info(f"Group ID: {GROUP_ID}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
