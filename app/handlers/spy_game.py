"""
Обработчики игры "Достать ножи".

Полнофункциональная игра для вечеринки с регистрацией игроков,
кольцевой системой заданий, подтверждением смертей и финальным отчётом.

Основные возможности:
- Регистрация реальных игроков через личку бота
- Тестовый режим с виртуальными игроками
- Кольцевое распределение целей (каждый убивает следующего в цепочке)
- Двухэтапное подтверждение смерти
- Автоматическое перераспределение целей после убийств
- Финальный отчёт с хронологией и путём победителя
- Персистентное SQLite хранилище

Игровая механика:
- Каждый игрок получает цель, оружие и локацию
- Жертва подтверждает смерть кнопкой "Я мёртв"
- Убийца получает цель жертвы с новым оружием/локацией
- Безопасная зона: "курилка" (убийства там запрещены)
- Игра продолжается до одного выжившего
"""

import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.constants import (
    MIN_ASSASSIN_PARTICIPANTS,
    MAX_ASSASSIN_PARTICIPANTS,
    DEFAULT_TEST_PLAYERS,
    SAFE_ZONE,
    DEFAULT_WEAPONS,
    DEFAULT_LOCATIONS,
)
from app.messages import Messages, ButtonLabels, Emojis
from app.callbacks import AssassinCallbacks
from app.keyboards import (
    get_assassin_admin_menu,
    get_assassin_registration_keyboard,
    get_assassin_player_menu,
    get_assassin_death_confirm_keyboard,
    get_assassin_test_count_keyboard,
    get_assassin_test_menu,
    get_assassin_test_player_list_keyboard,
    get_assassin_test_player_actions_keyboard,
    get_assassin_test_death_confirm_keyboard,
)
from app.states import AssassinState
from app.database import (
    get_active_game,
    create_game,
    get_game_by_id,
    update_game_status,
    create_player,
    get_player_by_tg_id,
    get_player_by_id,
    get_all_players,
    get_alive_players,
    mark_player_dead,
    count_players,
    create_contract,
    get_active_contract_for_assassin,
    get_active_contract_for_target,
    deactivate_contract,
    create_kill_log,
    get_all_kills,
    get_kills_by_killer,
    add_weapon,
    get_active_weapons,
    clear_weapons,
    add_location,
    get_active_locations,
    clear_locations,
)

logger = logging.getLogger(__name__)

assassin_router = Router()

ADMIN_ID = settings.bot.admin_id
GROUP_ID = settings.bot.group_id
TIMEZONE = ZoneInfo(settings.bot.timezone)


# === Вспомогательные функции ===


def get_mention_html(user_id: int, username: str | None, display_name: str) -> str:
    """Создаёт HTML-упоминание пользователя."""
    if username:
        return f'<a href="https://t.me/{username}">{display_name}</a>'
    return f'<a href="tg://user?id={user_id}">{display_name}</a>'


def distribute_targets(players: list) -> list[tuple[int, int]]:
    """
    Распределяет цели по кольцу.
    Возвращает список пар (убийца_id, жертва_id).
    """
    player_ids = [p["id"] for p in players]
    random.shuffle(player_ids)

    assignments = []
    for i in range(len(player_ids)):
        assassin = player_ids[i]
        target = player_ids[(i + 1) % len(player_ids)]
        assignments.append((assassin, target))

    return assignments


async def assign_contracts(game_id: int, assignments: list[tuple[int, int]]) -> None:
    """Создаёт контракты для всех игроков."""
    weapons = get_active_weapons()
    locations = get_active_locations()

    if not weapons:
        weapons = DEFAULT_WEAPONS
    if not locations:
        locations = DEFAULT_LOCATIONS

    for assassin_id, target_id in assignments:
        weapon = random.choice(weapons)
        location = random.choice(locations)
        create_contract(game_id, assassin_id, target_id, weapon, location)


async def send_contract_to_player(bot: Bot, game_id: int, player_id: int, tg_user_id: int | None) -> None:
    """Отправляет контракт игроку в личку."""
    if not tg_user_id:
        return  # Виртуальный игрок

    contract = get_active_contract_for_assassin(game_id, player_id)
    if not contract:
        return

    target = get_player_by_id(contract["target_player_id"])
    if not target:
        return

    message_text = Messages.ASSASSIN_YOUR_CONTRACT.format(
        target=target["mention_html"],
        weapon=contract["weapon_text"],
        location=contract["location_text"],
    )

    try:
        await bot.send_message(
            tg_user_id,
            message_text,
            parse_mode="HTML",
            reply_markup=get_assassin_player_menu(),
        )
    except Exception as e:
        logger.error(f"Не удалось отправить контракт игроку {tg_user_id}: {e}")


async def process_death(
    bot: Bot, game_id: int, victim_id: int, is_test: bool
) -> dict:
    """
    Обрабатывает смерть игрока.
    Возвращает информацию о результате.
    """
    game = get_game_by_id(game_id)
    if not game or game["status"] != "running":
        return {"success": False, "error": "Игра не идёт"}

    victim = get_player_by_id(victim_id)
    if not victim or not victim["is_alive"]:
        return {"success": False, "error": "Игрок уже мёртв"}

    # Найти контракт на жертву
    killer_contract = get_active_contract_for_target(game_id, victim_id)
    if not killer_contract:
        return {"success": False, "error": "Не найден контракт на эту жертву"}

    killer = get_player_by_id(killer_contract["assassin_player_id"])
    if not killer:
        return {"success": False, "error": "Не найден убийца"}

    # Найти контракт жертвы
    victim_contract = get_active_contract_for_assassin(game_id, victim_id)
    if not victim_contract:
        return {"success": False, "error": "Не найден контракт жертвы"}

    # Записать убийство
    create_kill_log(
        game_id,
        killer["id"],
        victim["id"],
        killer_contract["weapon_text"],
        killer_contract["location_text"],
        is_test,
    )

    # Пометить жертву мёртвой
    mark_player_dead(victim_id)

    # Деактивировать старые контракты
    deactivate_contract(killer_contract["id"])
    deactivate_contract(victim_contract["id"])

    # Проверить количество живых
    alive_players = get_alive_players(game_id)

    if len(alive_players) == 1:
        # Игра окончена
        winner = alive_players[0]
        update_game_status(
            game_id,
            "finished",
            finished_at=datetime.now(),
            winner_player_id=winner["id"],
        )

        # Отправить финальный отчёт
        await send_final_report(bot, game_id, is_test)

        return {
            "success": True,
            "game_finished": True,
            "winner": winner,
            "killer": killer,
            "victim": victim,
        }

    # Создать новый контракт для убийцы
    new_target_id = victim_contract["target_player_id"]

    weapons = get_active_weapons() or DEFAULT_WEAPONS
    locations = get_active_locations() or DEFAULT_LOCATIONS

    new_weapon = random.choice(weapons)
    new_location = random.choice(locations)

    create_contract(game_id, killer["id"], new_target_id, new_weapon, new_location)

    # Отправить новое задание убийце
    await send_new_contract_to_killer(bot, game_id, killer, new_target_id, new_weapon, new_location)

    return {
        "success": True,
        "game_finished": False,
        "killer": killer,
        "victim": victim,
        "new_target_id": new_target_id,
    }


async def send_new_contract_to_killer(
    bot: Bot, game_id: int, killer: dict, target_id: int, weapon: str, location: str
) -> None:
    """Отправляет новый контракт убийце."""
    if not killer["tg_user_id"]:
        return  # Виртуальный игрок

    target = get_player_by_id(target_id)
    if not target:
        return

    message_text = Messages.ASSASSIN_NEW_CONTRACT.format(
        target=target["mention_html"],
        weapon=weapon,
        location=location,
    )

    try:
        await bot.send_message(
            killer["tg_user_id"],
            message_text,
            parse_mode="HTML",
            reply_markup=get_assassin_player_menu(),
        )
    except Exception as e:
        logger.error(f"Не удалось отправить новый контракт игроку {killer['tg_user_id']}: {e}")


async def send_death_announcement(bot: Bot, game_id: int, victim: dict, is_test: bool) -> None:
    """Отправляет анонс смерти."""
    announcement = Messages.ASSASSIN_DEATH_ANNOUNCEMENT.format(
        victim=victim["display_name"]
    )

    if is_test:
        announcement = Messages.ASSASSIN_TEST_DEATH_ANNOUNCEMENT.format(
            victim=victim["display_name"]
        )
        try:
            await bot.send_message(ADMIN_ID, announcement, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось отправить тестовый анонс админу: {e}")
    else:
        try:
            await bot.send_message(GROUP_ID, announcement, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось отправить анонс в группу: {e}")


async def send_final_report(bot: Bot, game_id: int, is_test: bool) -> None:
    """Отправляет финальный отчёт."""
    game = get_game_by_id(game_id)
    if not game:
        return

    winner = get_player_by_id(game["winner_player_id"])
    if not winner:
        return

    all_kills = get_all_kills(game_id)
    winner_kills = get_kills_by_killer(game_id, winner["id"])

    # Хронология
    chronology_lines = []
    for kill in all_kills:
        # kill["killed_at"] уже datetime объект из SQLite
        killed_time = kill["killed_at"]
        if isinstance(killed_time, str):
            killed_time = datetime.fromisoformat(killed_time)
        killed_time = killed_time.astimezone(TIMEZONE)

        chronology_lines.append(
            Messages.ASSASSIN_KILL_ENTRY.format(
                time=killed_time.strftime("%H:%M"),
                killer=kill["killer_mention"],
                victim=kill["victim_mention"],
                location=kill["location_text"],
                weapon=kill["weapon_text"],
            )
        )

    chronology = Messages.ASSASSIN_CHRONOLOGY.format(kills="".join(chronology_lines))

    # Путь победителя
    winner_path_lines = []
    for kill in winner_kills:
        # kill["killed_at"] уже datetime объект из SQLite
        killed_time = kill["killed_at"]
        if isinstance(killed_time, str):
            killed_time = datetime.fromisoformat(killed_time)
        killed_time = killed_time.astimezone(TIMEZONE)

        winner_path_lines.append(
            Messages.ASSASSIN_KILL_ENTRY.format(
                time=killed_time.strftime("%H:%M"),
                killer=winner["mention_html"],
                victim=kill["victim_mention"],
                location=kill["location_text"],
                weapon=kill["weapon_text"],
            )
        )

    winner_path = ""
    if winner_path_lines:
        winner_path = Messages.ASSASSIN_WINNER_PATH.format(kills="".join(winner_path_lines))

    report = chronology + winner_path + "🎉 Поздравляем победителя!"

    final_message = Messages.ASSASSIN_GAME_FINISHED.format(
        winner=winner["mention_html"],
        report=report,
    )

    if is_test:
        final_message = f"🧪 TEST RESULT:\n\n{final_message}"
        try:
            await bot.send_message(ADMIN_ID, final_message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось отправить финальный отчёт админу: {e}")
    else:
        try:
            await bot.send_message(GROUP_ID, final_message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось отправить финальный отчёт в группу: {e}")


# === Обработчики админа ===


@assassin_router.message(
    F.text.in_([f"{Emojis.SPY} Шпион", "🔪 Достать ножи"]),
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
)
async def admin_assassin_menu(message: Message) -> None:
    """Показать меню игры."""
    await message.answer(
        Messages.ASSASSIN_MENU_TITLE,
        parse_mode="Markdown",
        reply_markup=get_assassin_admin_menu(),
    )


@assassin_router.callback_query(
    F.data == AssassinCallbacks.ADMIN_MENU,
    F.from_user.id == ADMIN_ID,
)
async def admin_assassin_menu_callback(callback: CallbackQuery) -> None:
    """Вернуться в меню игры."""
    await callback.message.edit_text(
        Messages.ASSASSIN_MENU_TITLE,
        parse_mode="Markdown",
        reply_markup=get_assassin_admin_menu(),
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data == AssassinCallbacks.OPEN_REGISTRATION,
    F.from_user.id == ADMIN_ID,
)
async def admin_open_registration(callback: CallbackQuery, bot: Bot) -> None:
    """Открыть регистрацию на игру."""
    game = get_active_game()

    if game and game["status"] == "registration":
        await callback.answer(Messages.ASSASSIN_REG_ALREADY_OPEN, show_alert=True)
        return

    if game and game["status"] == "running":
        await callback.answer(Messages.ASSASSIN_GAME_ALREADY_RUNNING, show_alert=True)
        return

    # Создать новую игру
    game_id = create_game(is_test_mode=False, group_chat_id=GROUP_ID)

    # Объявить в группу - сначала регистрация
    await bot.send_message(
        GROUP_ID,
        Messages.ASSASSIN_REGISTRATION_OPEN,
        parse_mode="Markdown",
    )

    # Затем устрашающее сообщение
    await bot.send_message(
        GROUP_ID,
        Messages.ASSASSIN_GAME_STARTING,
        parse_mode="Markdown",
    )

    await callback.message.edit_text(
        f"{Emojis.SUCCESS} {Messages.ASSASSIN_REG_OPENED}",
        reply_markup=get_assassin_admin_menu(),
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data == AssassinCallbacks.SET_WEAPONS,
    F.from_user.id == ADMIN_ID,
)
async def admin_set_weapons(callback: CallbackQuery, state: FSMContext) -> None:
    """Задать список оружий."""
    await state.set_state(AssassinState.waiting_for_weapons)
    await callback.message.edit_text(
        Messages.ASSASSIN_WEAPONS_PROMPT,
        parse_mode="Markdown",
    )
    await callback.answer()


@assassin_router.message(
    AssassinState.waiting_for_weapons,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
)
async def process_weapons_list(message: Message, state: FSMContext) -> None:
    """Обработать список оружий."""
    await state.clear()

    weapons = [line.strip() for line in message.text.split("\n") if line.strip()]

    clear_weapons()
    count = 0
    for weapon in weapons:
        add_weapon(weapon)
        count += 1

    await message.answer(
        f"{Emojis.SUCCESS} {Messages.ASSASSIN_WEAPONS_SAVED.format(count=count)}",
        reply_markup=get_assassin_admin_menu(),
    )


@assassin_router.callback_query(
    F.data == AssassinCallbacks.SET_LOCATIONS,
    F.from_user.id == ADMIN_ID,
)
async def admin_set_locations(callback: CallbackQuery, state: FSMContext) -> None:
    """Задать список локаций."""
    await state.set_state(AssassinState.waiting_for_locations)
    await callback.message.edit_text(
        Messages.ASSASSIN_LOCATIONS_PROMPT,
        parse_mode="Markdown",
    )
    await callback.answer()


@assassin_router.message(
    AssassinState.waiting_for_locations,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
)
async def process_locations_list(message: Message, state: FSMContext) -> None:
    """Обработать список локаций."""
    await state.clear()

    locations = [line.strip() for line in message.text.split("\n") if line.strip()]

    clear_locations()
    count = 0
    skipped = []

    for location in locations:
        if location.lower() == SAFE_ZONE.lower():
            skipped.append(location)
            continue
        add_location(location)
        count += 1

    response = f"{Emojis.SUCCESS} {Messages.ASSASSIN_LOCATIONS_SAVED.format(count=count)}"

    if skipped:
        for loc in skipped:
            response += f"\n{Messages.ASSASSIN_LOCATION_SAFE_ZONE_SKIP.format(location=loc)}"

    await message.answer(
        response,
        reply_markup=get_assassin_admin_menu(),
    )


@assassin_router.callback_query(
    F.data == AssassinCallbacks.SHOW_LISTS,
    F.from_user.id == ADMIN_ID,
)
async def admin_show_lists(callback: CallbackQuery) -> None:
    """Показать текущие списки оружий и локаций."""
    weapons = get_active_weapons() or DEFAULT_WEAPONS
    locations = get_active_locations() or DEFAULT_LOCATIONS

    weapons_text = "\n".join(f"• {w}" for w in weapons)
    locations_text = "\n".join(f"• {l}" for l in locations)

    response = Messages.ASSASSIN_LISTS_TITLE
    response += Messages.ASSASSIN_WEAPONS_LIST.format(count=len(weapons), list=weapons_text)
    response += Messages.ASSASSIN_LOCATIONS_LIST.format(count=len(locations), list=locations_text)

    await callback.message.edit_text(
        response,
        parse_mode="Markdown",
        reply_markup=get_assassin_admin_menu(),
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data == AssassinCallbacks.START_GAME,
    F.from_user.id == ADMIN_ID,
)
async def admin_start_game(callback: CallbackQuery, bot: Bot) -> None:
    """Начать игру."""
    game = get_active_game()

    if not game:
        await callback.answer(Messages.ASSASSIN_NO_ACTIVE_GAME, show_alert=True)
        return

    if game["status"] != "registration":
        await callback.answer(Messages.ASSASSIN_GAME_ALREADY_RUNNING, show_alert=True)
        return

    players_count = count_players(game["id"])

    if players_count < MIN_ASSASSIN_PARTICIPANTS:
        await callback.answer(Messages.ASSASSIN_MIN_PLAYERS, show_alert=True)
        return

    weapons = get_active_weapons()
    if not weapons:
        weapons = DEFAULT_WEAPONS

    locations = get_active_locations()
    if not locations:
        locations = DEFAULT_LOCATIONS

    if not weapons:
        await callback.answer(Messages.ASSASSIN_NO_WEAPONS, show_alert=True)
        return

    if not locations:
        await callback.answer(Messages.ASSASSIN_NO_LOCATIONS, show_alert=True)
        return

    # Получить всех игроков
    players = get_all_players(game["id"])
    players_data = [dict(p) for p in players]

    # Распределить цели
    assignments = distribute_targets(players_data)

    # Создать контракты
    await assign_contracts(game["id"], assignments)

    # Обновить статус игры
    update_game_status(game["id"], "running", started_at=datetime.now())

    # Отправить контракты игрокам
    for player in players:
        await send_contract_to_player(bot, game["id"], player["id"], player["tg_user_id"])

    # Объявить в группу или админу (если тест)
    if game["is_test_mode"]:
        # Сначала устрашающее сообщение
        await bot.send_message(
            ADMIN_ID,
            f"🧪 TEST:\n\n{Messages.ASSASSIN_GAME_STARTING}",
            parse_mode="Markdown",
        )
        # Затем старт
        await bot.send_message(
            ADMIN_ID,
            f"🧪 TEST:\n\n{Messages.ASSASSIN_GAME_STARTED}",
            parse_mode="Markdown",
        )
    else:
        # Сначала устрашающее сообщение
        await bot.send_message(
            GROUP_ID,
            Messages.ASSASSIN_GAME_STARTING,
            parse_mode="Markdown",
        )
        # Затем старт
        await bot.send_message(
            GROUP_ID,
            Messages.ASSASSIN_GAME_STARTED,
            parse_mode="Markdown",
        )

    if game["is_test_mode"]:
        await callback.message.edit_text(
            f"{Emojis.SUCCESS} {Messages.ASSASSIN_STARTED}\n\n"
            f"*Управляй виртуальными игроками:*\n"
            f"Нажми *«👥 Виртуальные игроки»* ниже",
            parse_mode="Markdown",
            reply_markup=get_assassin_test_menu(),
        )
    else:
        await callback.message.edit_text(
            f"{Emojis.SUCCESS} {Messages.ASSASSIN_STARTED}",
            reply_markup=get_assassin_admin_menu(),
        )
    await callback.answer()


@assassin_router.callback_query(
    F.data == AssassinCallbacks.RESET_GAME,
    F.from_user.id == ADMIN_ID,
)
async def admin_reset_game(callback: CallbackQuery) -> None:
    """Сбросить игру."""
    game = get_active_game()

    if not game:
        await callback.answer("Нет активной игры", show_alert=True)
        return

    # Завершить игру
    update_game_status(game["id"], "finished", finished_at=datetime.now())

    await callback.message.edit_text(
        f"{Emojis.SUCCESS} {Messages.ASSASSIN_RESET_DONE}",
        reply_markup=get_assassin_admin_menu(),
    )
    await callback.answer()


# === Тестовый режим ===


@assassin_router.callback_query(
    F.data == AssassinCallbacks.TEST_MODE,
    F.from_user.id == ADMIN_ID,
)
async def admin_test_mode(callback: CallbackQuery, state: FSMContext) -> None:
    """Запустить тестовый режим."""
    game = get_active_game()
    if game:
        await callback.answer(Messages.ASSASSIN_GAME_ALREADY_RUNNING, show_alert=True)
        return

    await state.set_state(AssassinState.waiting_for_test_count)
    await callback.message.edit_text(
        Messages.ASSASSIN_TEST_MODE_PROMPT,
        parse_mode="Markdown",
        reply_markup=get_assassin_test_count_keyboard(),
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data.startswith(f"{AssassinCallbacks.TEST_MODE}:"),
    F.from_user.id == ADMIN_ID,
)
async def admin_test_mode_default(callback: CallbackQuery, state: FSMContext) -> None:
    """Создать тестовую игру с дефолтным количеством."""
    count = int(callback.data.split(":")[-1])
    await create_test_game(callback.message, state, count)
    await callback.answer()


@assassin_router.message(
    AssassinState.waiting_for_test_count,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
)
async def process_test_count(message: Message, state: FSMContext) -> None:
    """Обработать количество виртуальных игроков."""
    try:
        count = int(message.text.strip())
        if count < MIN_ASSASSIN_PARTICIPANTS or count > MAX_ASSASSIN_PARTICIPANTS:
            await message.answer(Messages.ASSASSIN_TEST_INVALID_COUNT)
            return

        await create_test_game(message, state, count)
    except ValueError:
        await message.answer(Messages.ASSASSIN_TEST_INVALID_COUNT)


async def create_test_game(message: Message, state: FSMContext, count: int) -> None:
    """Создать тестовую игру."""
    await state.clear()

    # Создать игру
    game_id = create_game(is_test_mode=True, group_chat_id=GROUP_ID)

    # Создать виртуальных игроков
    for i in range(1, count + 1):
        name = f"Virtual #{i:02d}"
        create_player(
            game_id=game_id,
            display_name=name,
            mention_html=name,
            is_virtual=True,
        )

    await message.answer(
        f"{Emojis.SUCCESS} {Messages.ASSASSIN_TEST_CREATED.format(count=count)}",
        reply_markup=get_assassin_test_menu(),
    )


@assassin_router.callback_query(
    F.data == AssassinCallbacks.TEST_PLAYERS_LIST,
    F.from_user.id == ADMIN_ID,
)
async def admin_test_players_list(callback: CallbackQuery) -> None:
    """Показать список виртуальных игроков."""
    game = get_active_game()
    if not game:
        await callback.answer("Нет активной игры", show_alert=True)
        return

    players = get_all_players(game["id"])
    players_data = [dict(p) for p in players]

    await callback.message.edit_text(
        Messages.ASSASSIN_TEST_PLAYERS_LIST_TITLE,
        parse_mode="Markdown",
        reply_markup=get_assassin_test_player_list_keyboard(players_data),
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data.startswith(f"{AssassinCallbacks.TEST_SELECT_PLAYER}:"),
    F.from_user.id == ADMIN_ID,
)
async def admin_test_select_player(callback: CallbackQuery) -> None:
    """Показать информацию о виртуальном игроке."""
    player_id = int(callback.data.split(":")[-1])
    player = get_player_by_id(player_id)

    if not player:
        await callback.answer("Игрок не найден", show_alert=True)
        return

    game = get_game_by_id(player["game_id"])
    if not game:
        await callback.answer("Игра не найдена", show_alert=True)
        return

    status = Messages.ASSASSIN_TEST_PLAYER_ALIVE if player["is_alive"] else Messages.ASSASSIN_TEST_PLAYER_DEAD

    contract_text = ""
    if player["is_alive"] and game["status"] == "running":
        contract = get_active_contract_for_assassin(game["id"], player["id"])
        if contract:
            target = get_player_by_id(contract["target_player_id"])
            if target:
                contract_text = Messages.ASSASSIN_YOUR_CONTRACT.format(
                    target=target["display_name"],
                    weapon=contract["weapon_text"],
                    location=contract["location_text"],
                )

    message_text = Messages.ASSASSIN_TEST_PLAYER_INFO.format(
        name=player["display_name"],
        status=status,
        contract=contract_text,
    )

    await callback.message.edit_text(
        message_text,
        parse_mode="HTML",
        reply_markup=get_assassin_test_player_actions_keyboard(player["id"], player["is_alive"]),
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data.startswith(f"{AssassinCallbacks.TEST_KILL_PLAYER}:"),
    F.from_user.id == ADMIN_ID,
)
async def admin_test_kill_player(callback: CallbackQuery) -> None:
    """Показать подтверждение смерти виртуального игрока."""
    player_id = int(callback.data.split(":")[-1])
    player = get_player_by_id(player_id)

    if not player:
        await callback.answer("Игрок не найден", show_alert=True)
        return

    game = get_game_by_id(player["game_id"])
    if not game:
        await callback.answer("Игра не найдена", show_alert=True)
        return

    # Найти убийцу
    killer_contract = get_active_contract_for_target(game["id"], player["id"])
    if not killer_contract:
        await callback.answer("Не найден контракт на этого игрока", show_alert=True)
        return

    killer = get_player_by_id(killer_contract["assassin_player_id"])
    if not killer:
        await callback.answer("Не найден убийца", show_alert=True)
        return

    message_text = Messages.ASSASSIN_DEATH_CONFIRM_PROMPT.format(
        killer=killer["display_name"]
    )

    await callback.message.edit_text(
        message_text,
        parse_mode="HTML",
        reply_markup=get_assassin_test_death_confirm_keyboard(player["id"]),
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data.startswith(f"{AssassinCallbacks.TEST_CONFIRM_KILL}:"),
    F.from_user.id == ADMIN_ID,
)
async def admin_test_confirm_kill(callback: CallbackQuery, bot: Bot) -> None:
    """Подтвердить смерть виртуального игрока."""
    player_id = int(callback.data.split(":")[-1])
    player = get_player_by_id(player_id)

    if not player:
        await callback.answer("Игрок не найден", show_alert=True)
        return

    game = get_game_by_id(player["game_id"])
    if not game:
        await callback.answer("Игра не найдена", show_alert=True)
        return

    # Обработать смерть
    result = await process_death(bot, game["id"], player["id"], is_test=True)

    if not result["success"]:
        await callback.answer(result.get("error", "Ошибка"), show_alert=True)
        return

    # Отправить анонс
    await send_death_announcement(bot, game["id"], player, is_test=True)

    if result["game_finished"]:
        await callback.message.edit_text(
            "🏆 Игра завершена! Финальный отчёт отправлен.",
            reply_markup=get_assassin_admin_menu(),
        )
    else:
        await callback.message.edit_text(
            f"☠️ {player['display_name']} мёртв!",
            reply_markup=get_assassin_test_menu(),
        )

    await callback.answer()


# === Обработчики игроков ===


@assassin_router.message(
    CommandStart(),
    F.chat.type == ChatType.PRIVATE,
    ~(F.from_user.id == ADMIN_ID),
)
async def cmd_start_player(message: Message) -> None:
    """Команда /start для игрока."""
    game = get_active_game()

    if not game:
        await message.answer(Messages.ASSASSIN_NO_ACTIVE_GAME)
        return

    if game["status"] == "registration":
        await message.answer(
            Messages.ASSASSIN_NO_ACTIVE_GAME + "\n\nИспользуй кнопку для регистрации:",
            reply_markup=get_assassin_registration_keyboard(),
        )
        return

    if game["status"] == "running":
        player = get_player_by_tg_id(game["id"], message.from_user.id)
        if not player:
            await message.answer(Messages.ASSASSIN_NOT_IN_GAME)
            return

        if not player["is_alive"]:
            await message.answer(Messages.ASSASSIN_ALREADY_DEAD)
            return

        await message.answer(
            "Игра идёт! Используй кнопки:",
            reply_markup=get_assassin_player_menu(),
        )
        return


@assassin_router.callback_query(
    F.data == AssassinCallbacks.REGISTER,
)
async def player_register(callback: CallbackQuery) -> None:
    """Регистрация игрока."""
    game = get_active_game()

    if not game:
        await callback.answer(Messages.ASSASSIN_NO_ACTIVE_GAME, show_alert=True)
        return

    if game["status"] != "registration":
        await callback.answer(Messages.ASSASSIN_REG_CLOSED, show_alert=True)
        return

    # Проверить, не зарегистрирован ли уже
    existing = get_player_by_tg_id(game["id"], callback.from_user.id)
    if existing:
        await callback.answer(Messages.ASSASSIN_ALREADY_REGISTERED, show_alert=True)
        return

    # Зарегистрировать
    display_name = callback.from_user.full_name
    username = callback.from_user.username
    mention_html = get_mention_html(callback.from_user.id, username, display_name)

    create_player(
        game_id=game["id"],
        display_name=display_name,
        mention_html=mention_html,
        tg_user_id=callback.from_user.id,
        username=username,
        is_virtual=False,
    )

    await callback.message.edit_text(
        Messages.ASSASSIN_REGISTERED.format(mention=mention_html),
        parse_mode="HTML",
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data == AssassinCallbacks.SHOW_CONTRACT,
)
async def player_show_contract(callback: CallbackQuery) -> None:
    """Показать контракт игроку."""
    game = get_active_game()

    if not game or game["status"] != "running":
        await callback.answer(Messages.ASSASSIN_NO_ACTIVE_GAME, show_alert=True)
        return

    player = get_player_by_tg_id(game["id"], callback.from_user.id)
    if not player:
        await callback.answer(Messages.ASSASSIN_NOT_IN_GAME, show_alert=True)
        return

    if not player["is_alive"]:
        await callback.answer(Messages.ASSASSIN_ALREADY_DEAD, show_alert=True)
        return

    contract = get_active_contract_for_assassin(game["id"], player["id"])
    if not contract:
        await callback.answer("Нет активного контракта", show_alert=True)
        return

    target = get_player_by_id(contract["target_player_id"])
    if not target:
        await callback.answer("Цель не найдена", show_alert=True)
        return

    message_text = Messages.ASSASSIN_YOUR_CONTRACT.format(
        target=target["mention_html"],
        weapon=contract["weapon_text"],
        location=contract["location_text"],
    )

    await callback.message.edit_text(
        message_text,
        parse_mode="HTML",
        reply_markup=get_assassin_player_menu(),
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data == AssassinCallbacks.I_AM_DEAD,
)
async def player_i_am_dead(callback: CallbackQuery) -> None:
    """Игрок нажал 'Я мёртв'."""
    game = get_active_game()

    if not game or game["status"] != "running":
        await callback.answer(Messages.ASSASSIN_NO_ACTIVE_GAME, show_alert=True)
        return

    player = get_player_by_tg_id(game["id"], callback.from_user.id)
    if not player:
        await callback.answer(Messages.ASSASSIN_NOT_IN_GAME, show_alert=True)
        return

    if not player["is_alive"]:
        await callback.answer(Messages.ASSASSIN_ALREADY_DEAD, show_alert=True)
        return

    # Найти убийцу
    killer_contract = get_active_contract_for_target(game["id"], player["id"])
    if not killer_contract:
        await callback.answer("Не найден контракт на тебя", show_alert=True)
        return

    killer = get_player_by_id(killer_contract["assassin_player_id"])
    if not killer:
        await callback.answer("Не найден убийца", show_alert=True)
        return

    # Показать подтверждение
    message_text = Messages.ASSASSIN_DEATH_CONFIRM_PROMPT.format(
        killer=killer["mention_html"]
    )

    await callback.message.edit_text(
        message_text,
        parse_mode="HTML",
        reply_markup=get_assassin_death_confirm_keyboard(),
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data == AssassinCallbacks.CONFIRM_DEATH,
)
async def player_confirm_death(callback: CallbackQuery, bot: Bot) -> None:
    """Подтверждение смерти игроком."""
    game = get_active_game()

    if not game or game["status"] != "running":
        await callback.answer(Messages.ASSASSIN_NO_ACTIVE_GAME, show_alert=True)
        return

    player = get_player_by_tg_id(game["id"], callback.from_user.id)
    if not player:
        await callback.answer(Messages.ASSASSIN_NOT_IN_GAME, show_alert=True)
        return

    # Обработать смерть
    result = await process_death(bot, game["id"], player["id"], is_test=False)

    if not result["success"]:
        await callback.answer(result.get("error", "Ошибка"), show_alert=True)
        return

    # Отправить анонс
    await send_death_announcement(bot, game["id"], player, is_test=False)

    await callback.message.edit_text(
        Messages.ASSASSIN_DEATH_CONFIRMED,
        parse_mode="HTML",
    )
    await callback.answer()


@assassin_router.callback_query(
    F.data == AssassinCallbacks.CANCEL_DEATH,
)
async def player_cancel_death(callback: CallbackQuery) -> None:
    """Отмена подтверждения смерти."""
    await callback.message.edit_text(
        "Отменено. Используй кнопки:",
        reply_markup=get_assassin_player_menu(),
    )
    await callback.answer()
