"""
Утилиты для турнирной системы бир-понга.
"""

import math
import random
from typing import Optional

from app.constants import TOURNAMENT_TEAM_SIZE_THRESHOLD
from app.messages import TEAM_NAMES
from app.storage import Match, Tournament


def determine_team_size(num_participants: int) -> int:
    """
    Определить оптимальный размер команды.

    Логика:
    - До 11 человек включительно -> команды по 2
    - 12+ человек -> команды по 3
    """
    if num_participants <= TOURNAMENT_TEAM_SIZE_THRESHOLD:
        return 2
    else:
        return 3


def create_teams(participants: list[str], team_size: int) -> list[tuple[str, list[str]]]:
    """
    Разбить участников на команды и назначить названия.

    Args:
        participants: Список имен участников
        team_size: Размер команды (2 или 3)

    Returns:
        Список кортежей (team_name, [members])
    """
    # Перемешать участников
    shuffled = participants.copy()
    random.shuffle(shuffled)

    # Разбить на команды
    teams = []
    for i in range(0, len(shuffled), team_size):
        team_members = shuffled[i : i + team_size]
        teams.append(team_members)

    # Назначить названия из TEAM_NAMES
    # Развернуть пары в плоский список
    all_team_names = [name for pair in TEAM_NAMES for name in pair]

    # Выбрать случайные названия без повторений
    selected_names = random.sample(all_team_names, k=min(len(teams), len(all_team_names)))

    return [(name, members) for name, members in zip(selected_names, teams)]


def generate_single_elimination_bracket(
    teams: list[tuple[str, list[str]]]
) -> dict[str, Match]:
    """
    Генерирует single elimination сетку.

    Args:
        teams: Список команд [(team_name, [members]), ...]

    Returns:
        Словарь {match_id: Match, ...}
    """
    num_teams = len(teams)

    # Определить количество раундов (log2 округление вверх)
    max_rounds = math.ceil(math.log2(num_teams))

    matches = {}

    # Первый раунд - создать матчи из всех команд
    round_1_matches = []
    for i in range(0, len(teams), 2):
        if i + 1 < len(teams):
            # Обычный матч
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
        else:
            # Bye - команда проходит автоматически
            match_id = f"R1M{i // 2 + 1}"
            match = Match(
                match_id=match_id,
                round_number=1,
                team1_name=teams[i][0],
                team2_name="BYE",
                team1_members=teams[i][1],
                team2_members=[],
                winner_team=1,
                status="finished",
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
            if i + 1 < len(previous_round):
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
            team1_members_str = ", ".join(match.team1_members)
            team1_display = f"{match.team1_name} ({team1_members_str})"

            if match.team2_name != "BYE":
                team2_members_str = ", ".join(match.team2_members)
                team2_display = f"{match.team2_name} ({team2_members_str})"
            else:
                team2_display = "BYE"

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
            pending_ids = [m.match_id for m in pending_matches[:3]]
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
