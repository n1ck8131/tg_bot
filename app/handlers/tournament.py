"""
Обработчики турнирной системы бир-понга.
"""

import logging
from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.constants import MIN_TOURNAMENT_PARTICIPANTS, MAX_TOURNAMENT_PARTICIPANTS
from app.messages import Messages, Emojis
from app.callbacks import TournamentCallbacks, AdminCallbacks
from app.keyboards import (
    get_tournament_match_selection_keyboard,
    get_match_winner_keyboard,
    get_tournament_control_keyboard,
)
from app.states import TournamentState
from app.storage import tournament_storage
from app.tournament_utils import (
    create_teams,
    generate_single_elimination_bracket,
    format_bracket_for_display,
    get_pending_matches,
)

logger = logging.getLogger(__name__)

tournament_router = Router()

ADMIN_ID = settings.bot.admin_id
GROUP_ID = settings.bot.group_id


# === Создание турнира ===


@tournament_router.message(
    F.text == f"{Emojis.TOURNAMENT} Турнир",
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
)
async def start_tournament_creation(message: Message, state: FSMContext) -> None:
    """Начало создания турнира."""
    if tournament_storage.get_current():
        await message.answer(f"{Emojis.ERROR} {Messages.TOURNAMENT_ALREADY_ACTIVE}")
        return

    await state.set_state(TournamentState.waiting_for_participants)
    await message.answer(Messages.TOURNAMENT_PROMPT, parse_mode="Markdown")


@tournament_router.callback_query(
    F.data == AdminCallbacks.TOURNAMENT,
    F.from_user.id == ADMIN_ID
)
async def admin_callback_tournament(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало создания турнира через inline-кнопку."""
    if tournament_storage.get_current():
        await callback.message.answer(f"{Emojis.ERROR} {Messages.TOURNAMENT_ALREADY_ACTIVE}")
        await callback.answer()
        return

    await state.set_state(TournamentState.waiting_for_participants)
    await callback.message.answer(Messages.TOURNAMENT_PROMPT, parse_mode="Markdown")
    await callback.answer()


@tournament_router.message(
    TournamentState.waiting_for_participants,
    F.chat.type == ChatType.PRIVATE,
    F.from_user.id == ADMIN_ID,
)
async def process_tournament_participants(
    message: Message, bot: Bot, state: FSMContext
) -> None:
    """Обработка списка участников и создание турнира."""
    await state.clear()

    # Парсинг участников
    participants = [p.strip() for p in message.text.split(",") if p.strip()]

    # Валидация
    if len(participants) < MIN_TOURNAMENT_PARTICIPANTS:
        await message.answer(f"{Emojis.ERROR} {Messages.TOURNAMENT_MIN_PARTICIPANTS}")
        return

    if len(participants) > MAX_TOURNAMENT_PARTICIPANTS:
        await message.answer(
            f"{Emojis.ERROR} {Messages.TOURNAMENT_MAX_PARTICIPANTS.format(max=MAX_TOURNAMENT_PARTICIPANTS)}"
        )
        return

    # Создать команды
    try:
        teams = create_teams(participants)
    except ValueError as e:
        await message.answer(
            f"{Emojis.ERROR} {str(e)}\n\n"
            f"Невозможно создать турнир с {len(participants)} участниками.\n"
            f"Попробуйте другое количество."
        )
        return

    # Сгенерировать bracket
    try:
        matches = generate_single_elimination_bracket(teams)
    except ValueError as e:
        await message.answer(
            f"{Emojis.ERROR} {str(e)}\n\n"
            f"Внутренняя ошибка при создании турнирной сетки."
        )
        return

    # Создать турнир в storage
    tournament = tournament_storage.create_tournament(
        participants=participants, matches=matches
    )

    # Форматировать сетку
    bracket_text = format_bracket_for_display(tournament)

    # Отправить в группу
    sent = await bot.send_message(
        GROUP_ID, f"{bracket_text}", parse_mode="Markdown"
    )

    # Сохранить message_id для редактирования
    tournament.bracket_message_id = sent.message_id

    # Отправить админу управление
    await message.answer(
        Messages.TOURNAMENT_CREATED,
        reply_markup=get_tournament_control_keyboard(tournament),
    )


# === Просмотр сетки ===


@tournament_router.callback_query(
    F.data == TournamentCallbacks.VIEW_BRACKET, F.from_user.id == ADMIN_ID
)
async def view_tournament_bracket(callback: CallbackQuery) -> None:
    """Показать текущую сетку турнира."""
    tournament = tournament_storage.get_current()

    if not tournament:
        await callback.message.answer(f"{Emojis.ERROR} {Messages.TOURNAMENT_NO_ACTIVE}")
        await callback.answer()
        return

    bracket_text = format_bracket_for_display(tournament)

    try:
        await callback.message.edit_text(
            bracket_text,
            parse_mode="Markdown",
            reply_markup=get_tournament_control_keyboard(tournament),
        )
        await callback.answer("Сетка обновлена")
    except TelegramBadRequest as e:
        # Если сообщение не изменилось, просто уведомляем пользователя
        if "message is not modified" in str(e):
            await callback.answer("Сетка уже актуальна", show_alert=False)
        else:
            logger.error(f"Telegram API error при обновлении сетки: {e}")
            await callback.answer("Ошибка при обновлении", show_alert=True)
    except Exception as e:
        logger.exception(f"Unexpected error при обновлении сетки: {e}")
        await callback.answer("Ошибка при обновлении", show_alert=True)


# === Выбор матча для ввода результата ===


@tournament_router.callback_query(
    F.data == TournamentCallbacks.SELECT_MATCH, F.from_user.id == ADMIN_ID
)
async def select_match_for_result(callback: CallbackQuery) -> None:
    """Показать список матчей для ввода результата."""
    tournament = tournament_storage.get_current()

    if not tournament:
        await callback.message.answer(f"{Emojis.ERROR} {Messages.TOURNAMENT_NO_ACTIVE}")
        await callback.answer()
        return

    pending_matches = get_pending_matches(tournament)

    if not pending_matches:
        await callback.answer(Messages.TOURNAMENT_ALL_MATCHES_COMPLETE, show_alert=True)
        return

    await callback.message.edit_text(
        Messages.TOURNAMENT_SELECT_MATCH,
        reply_markup=get_tournament_match_selection_keyboard(tournament),
    )
    await callback.answer()


@tournament_router.callback_query(
    F.data.startswith(f"{TournamentCallbacks.SELECT_MATCH}:"), F.from_user.id == ADMIN_ID
)
async def show_match_winner_selection(callback: CallbackQuery) -> None:
    """Показать кнопки выбора победителя для матча."""
    match_id = callback.data.split(":")[-1]
    tournament = tournament_storage.get_current()

    if not tournament or match_id not in tournament.matches:
        await callback.answer(Messages.TOURNAMENT_MATCH_NOT_FOUND, show_alert=True)
        return

    match = tournament.matches[match_id]

    await callback.message.edit_text(
        Messages.TOURNAMENT_MATCH_RESULT_PROMPT.format(match_id=match_id),
        parse_mode="Markdown",
        reply_markup=get_match_winner_keyboard(match),
    )
    await callback.answer()


# === Установка победителя ===


@tournament_router.callback_query(
    F.data.regexp(r"^tournament:win[12]:"), F.from_user.id == ADMIN_ID
)
async def set_match_winner(callback: CallbackQuery, bot: Bot) -> None:
    """Установить победителя матча."""
    # Парсинг: tournament:win1:R1M1 или tournament:win2:R1M1
    parts = callback.data.split(":")
    winner_team = 1 if parts[1] == "win1" else 2
    match_id = parts[2]

    tournament = tournament_storage.get_current()

    if not tournament or match_id not in tournament.matches:
        logger.error(f"Турнир не найден или матч {match_id} не существует")
        await callback.answer(Messages.TOURNAMENT_MATCH_NOT_FOUND, show_alert=True)
        return

    match = tournament.matches[match_id]

    # Установить победителя
    tournament_storage.set_match_winner(match_id, winner_team)

    # Продвинуть победителя в следующий раунд
    next_match_id = tournament_storage.advance_winner(match_id)

    # Обновить сетку в группе
    bracket_text = format_bracket_for_display(tournament)
    if tournament.bracket_message_id:
        try:
            await bot.edit_message_text(
                text=bracket_text,
                chat_id=GROUP_ID,
                message_id=tournament.bracket_message_id,
                parse_mode="Markdown",
            )
        except TelegramBadRequest as e:
            logger.error(f"Telegram API error при обновлении сетки: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error при обновлении сетки: {e}")

    # Проверяем, был ли это финальный матч
    match = tournament.matches[match_id]
    is_final = match.round_number == tournament.max_rounds

    if is_final:
        # Автоматически завершаем турнир и объявляем победителя
        tournament_storage.finish_tournament()

        await bot.send_message(
            GROUP_ID,
            Messages.TOURNAMENT_FINISHED.format(
                winner_team=tournament.winner_team,
                winner_members=", ".join(tournament.winner_members or []),
            ),
            parse_mode="Markdown",
        )

        tournament_storage.clear()

        await callback.message.edit_text(
            f"🏆 Турнир завершен!\n\n"
            f"Победитель: {tournament.winner_team}\n"
            f"Участники: {', '.join(tournament.winner_members or [])}"
        )
        await callback.answer("🎉 Победитель объявлен!")
    else:
        # Уведомить админа
        await callback.message.edit_text(
            Messages.TOURNAMENT_MATCH_UPDATED.format(match_id=match_id),
            parse_mode="Markdown",
            reply_markup=get_tournament_control_keyboard(tournament),
        )
        await callback.answer(Messages.TOURNAMENT_RESULT_RECORDED)


# === Переход к следующему раунду ===


@tournament_router.callback_query(
    F.data == TournamentCallbacks.NEXT_ROUND, F.from_user.id == ADMIN_ID
)
async def advance_to_next_round(callback: CallbackQuery, bot: Bot) -> None:
    """Перейти к следующему раунду."""
    tournament = tournament_storage.get_current()

    if not tournament:
        await callback.answer(Messages.TOURNAMENT_NO_ACTIVE_ALERT, show_alert=True)
        return

    if not tournament_storage.check_round_complete():
        await callback.answer(Messages.TOURNAMENT_ROUND_NOT_COMPLETE, show_alert=True)
        return

    # Переход к следующему раунду
    tournament_storage.advance_to_next_round()

    # Обновить сетку
    bracket_text = format_bracket_for_display(tournament)
    if tournament.bracket_message_id:
        try:
            await bot.edit_message_text(
                text=bracket_text,
                chat_id=GROUP_ID,
                message_id=tournament.bracket_message_id,
                parse_mode="Markdown",
            )
        except TelegramBadRequest as e:
            logger.error(f"Telegram API error при обновлении сетки: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error при обновлении сетки: {e}")

    # Объявление в группу
    await bot.send_message(
        GROUP_ID,
        Messages.TOURNAMENT_ROUND_COMPLETE.format(round_num=tournament.current_round - 1),
        parse_mode="Markdown",
    )

    # Обновить админку
    await callback.message.edit_text(
        Messages.TOURNAMENT_ROUND_STARTED.format(round=tournament.current_round),
        reply_markup=get_tournament_control_keyboard(tournament),
    )
    await callback.answer()


# === Завершение турнира ===


@tournament_router.callback_query(
    F.data == TournamentCallbacks.FINISH, F.from_user.id == ADMIN_ID
)
async def finish_tournament(callback: CallbackQuery, bot: Bot) -> None:
    """Завершить турнир и объявить победителя."""
    tournament = tournament_storage.get_current()

    if not tournament:
        await callback.answer(Messages.TOURNAMENT_NO_ACTIVE_ALERT, show_alert=True)
        return

    # Завершить турнир
    tournament_storage.finish_tournament()

    # Объявить победителя в группе
    await bot.send_message(
        GROUP_ID,
        Messages.TOURNAMENT_FINISHED.format(
            winner_team=tournament.winner_team,
            winner_members=", ".join(tournament.winner_members or []),
        ),
        parse_mode="Markdown",
    )

    # Очистить турнир
    tournament_storage.clear()

    await callback.message.edit_text("🏆 Турнир завершен!")
    await callback.answer(Messages.TOURNAMENT_WINNER_CONGRATS)


# === Отмена ===


@tournament_router.callback_query(
    F.data == TournamentCallbacks.CANCEL, F.from_user.id == ADMIN_ID
)
async def cancel_action(callback: CallbackQuery) -> None:
    """Отменить текущее действие."""
    tournament = tournament_storage.get_current()

    if tournament:
        bracket_text = format_bracket_for_display(tournament)
        await callback.message.edit_text(
            bracket_text,
            parse_mode="Markdown",
            reply_markup=get_tournament_control_keyboard(tournament),
        )
    else:
        await callback.message.edit_text(Messages.TOURNAMENT_ACTION_CANCELLED)

    await callback.answer()
