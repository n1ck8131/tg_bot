"""
Утилиты для турнирной системы бир-понга.
"""

import math
import random
from typing import Optional

from app.messages import TEAM_NAMES
from app.storage import Match, Tournament
from app.constants import MAX_PENDING_MATCHES_DISPLAY


def create_teams(participants: list[str]) -> list[tuple[str, list[str]]]:
    """
    Разбить участников на команды и назначить названия.

    Правила:
    - Минимум 4 участника для турнира
    - Количество команд всегда степень двойки (2, 4, 8, 16...)
    - В команде минимум 2, максимум 4 человека
    - Оптимальный размер команды: 3 человека
    - NO BYE матчей - сетка всегда симметричная

    Args:
        participants: Список имен участников

    Returns:
        Список кортежей (team_name, [members])

    Raises:
        ValueError: Если меньше 4 участников
    """
    num_participants = len(participants)

    if num_participants < 4:
        raise ValueError("Минимум 4 участника для турнира")

    # Находим оптимальное количество команд (степень двойки)
    # Пробуем разные степени двойки и выбираем ту, где средний размер команды ближе к 3

    best_num_teams = None
    best_score = float('inf')

    # Проверяем степени двойки: 2, 4, 8, 16, 32, 64
    # Максимум 64 команды (для 256 участников при размере команды 4)
    for power in range(1, 7):
        num_teams = 2 ** power

        # Минимум участников для этого количества команд (по 2 в каждой)
        min_participants = num_teams * 2
        # Максимум участников для этого количества команд (по 4 в каждой)
        max_participants = num_teams * 4

        # Проверяем, подходит ли это количество команд
        if min_participants <= num_participants <= max_participants:
            # Вычисляем средний размер команды
            avg_team_size = num_participants / num_teams
            # Оцениваем, насколько далеко от оптимального (3)
            score = abs(avg_team_size - 3.0)

            # Выбираем наименьшее количество команд с лучшим score
            # Это предпочитает меньше команд (больше людей в команде) при равном score
            if score < best_score or (score == best_score and (best_num_teams is None or num_teams < best_num_teams)):
                best_score = score
                best_num_teams = num_teams

    if best_num_teams is None:
        raise ValueError(
            f"Невозможно создать команды для {num_participants} участников "
            f"(слишком много участников или невозможно распределить по командам 2-4 человека)"
        )

    num_teams = best_num_teams

    # Распределяем участников по командам
    # Стараемся сделать команды максимально равными по размеру
    base_size = num_participants // num_teams
    extra = num_participants % num_teams

    # Перемешать участников
    shuffled = participants.copy()
    random.shuffle(shuffled)

    # Создаем команды
    teams = []
    idx = 0

    for i in range(num_teams):
        # Первые 'extra' команд получают на одного участника больше
        size = base_size + (1 if i < extra else 0)
        teams.append(shuffled[idx:idx + size])
        idx += size

    # Назначить названия
    all_team_names = [name for pair in TEAM_NAMES for name in pair]

    # Если названий не хватает, генерируем дополнительные
    if len(all_team_names) < len(teams):
        for i in range(len(all_team_names) + 1, len(teams) + 1):
            all_team_names.append(f"Команда {i}")

    selected_names = random.sample(all_team_names, k=len(teams))

    return [(name, members) for name, members in zip(selected_names, teams)]


def generate_single_elimination_bracket(
    teams: list[tuple[str, list[str]]]
) -> dict[str, Match]:
    """
    Генерирует single elimination сетку.

    Количество команд должно быть степенью двойки (2, 4, 8, 16...).
    Не создает BYE матчей - сетка полностью симметричная.

    Args:
        teams: Список команд [(team_name, [members]), ...]

    Returns:
        Словарь {match_id: Match, ...}

    Raises:
        ValueError: Если количество команд не степень двойки
    """
    num_teams = len(teams)

    # Проверяем, что количество команд - степень двойки
    if num_teams < 2 or (num_teams & (num_teams - 1)) != 0:
        raise ValueError(f"Количество команд должно быть степенью двойки (2, 4, 8...), получено: {num_teams}")

    # Определить количество раундов (log2)
    max_rounds = int(math.log2(num_teams))

    matches = {}

    # Первый раунд - создать матчи из всех команд (пары)
    round_1_matches = []
    for i in range(0, len(teams), 2):
        match_id = f"R1M{i // 2 + 1}"
        match = Match(
            match_id=match_id,
            round_number=1,
            team1_name=teams[i][0],
            team2_name=teams[i + 1][0],
            team1_members=teams[i][1],
            team2_members=teams[i + 1][1],
        )
        matches[match_id] = match
        round_1_matches.append(match_id)

    # Создать остальные раунды (пустые матчи)
    previous_round = round_1_matches
    for round_num in range(2, max_rounds + 1):
        current_round = []
        for i in range(0, len(previous_round), 2):
            match_id = f"R{round_num}M{i // 2 + 1}"
            match = Match(
                match_id=match_id,
                round_number=round_num,
                team1_name="TBD",
                team2_name="TBD",
                team1_members=[],
                team2_members=[],
            )
            matches[match_id] = match
            current_round.append(match_id)

            # Связать предыдущие матчи с этим
            matches[previous_round[i]].next_match_id = match_id
            matches[previous_round[i + 1]].next_match_id = match_id

        previous_round = current_round

    return matches


def format_bracket_for_display(tournament: Tournament) -> str:
    """
    Форматировать сетку для отображения в чате.

    Args:
        tournament: Турнир

    Returns:
        Форматированный текст сетки
    """
    lines = ["🏆 *ТУРНИР БИР-ПОНГА* 🏆\n"]

    # Группировка матчей по раундам
    rounds: dict[int, list[Match]] = {}
    for match in tournament.matches.values():
        if match.round_number not in rounds:
            rounds[match.round_number] = []
        rounds[match.round_number].append(match)

    # Названия раундов (динамическое определение)
    def get_round_name(round_num: int, max_round: int) -> str:
        rounds_from_end = max_round - round_num
        if rounds_from_end == 0:
            return "ФИНАЛ"
        elif rounds_from_end == 1:
            return "1/2 ФИНАЛА"
        elif rounds_from_end == 2:
            return "1/4 ФИНАЛА"
        elif rounds_from_end == 3:
            return "1/8 ФИНАЛА"
        else:
            return f"РАУНД {round_num}"

    for round_num in sorted(rounds.keys()):
        round_matches = rounds[round_num]
        round_name = get_round_name(round_num, tournament.max_rounds)
        lines.append(f"\n*{round_name}:*\n")

        for match in sorted(round_matches, key=lambda m: m.match_id):
            status_emoji = "✅" if match.status == "finished" else "⏳"
            winner_indicator_1 = " 🏆" if match.winner_team == 1 else ""
            winner_indicator_2 = " 🏆" if match.winner_team == 2 else ""

            # Форматирование команд
            team1_members_str = ", ".join(match.team1_members) if match.team1_members else ""
            team1_display = f"{match.team1_name} ({team1_members_str})" if team1_members_str else match.team1_name

            team2_members_str = ", ".join(match.team2_members) if match.team2_members else ""
            team2_display = f"{match.team2_name} ({team2_members_str})" if team2_members_str else match.team2_name

            lines.append(
                f"{status_emoji} `{match.match_id}`: "
                f"🔴 {team1_display}{winner_indicator_1} vs "
                f"🔵 {team2_display}{winner_indicator_2}"
            )

    # Текущий статус
    if tournament.status == "finished":
        winner_members_str = ", ".join(tournament.winner_members or [])
        lines.append(
            f"\n\n🎉 *ПОБЕДИТЕЛИ:* {tournament.winner_team} ({winner_members_str})"
        )
    else:
        pending_matches = [m for m in tournament.matches.values() if m.status == "pending"]
        if pending_matches:
            pending_ids = [m.match_id for m in pending_matches[:MAX_PENDING_MATCHES_DISPLAY]]
            lines.append(f"\n\n⏳ Ожидание результатов: {', '.join(pending_ids)}")

    return "\n".join(lines)


def get_pending_matches(tournament: Tournament) -> list[Match]:
    """
    Получить список незавершенных матчей текущего раунда.

    Args:
        tournament: Турнир

    Returns:
        Список незавершенных матчей
    """
    return [
        match
        for match in tournament.matches.values()
        if match.status == "pending" and match.round_number == tournament.current_round
    ]
