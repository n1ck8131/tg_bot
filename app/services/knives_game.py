"""Сервис для игры 'Достать ножи'."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from app.config import settings
from app.constants import TIMEZONE

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)

ADMIN_ID = settings.bot.admin_id
GROUP_ID = settings.bot.group_id


class KnivesGameService:
    """Сервис для работы с игрой 'Достать ножи'."""

    @staticmethod
    def format_kill_chronology(game_id: int) -> str:
        """Форматирует хронологию убийств."""
        from app.database import get_all_kills
        from app.messages import Messages

        all_kills = get_all_kills(game_id)
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

        return Messages.ASSASSIN_CHRONOLOGY.format(kills="".join(chronology_lines))

    @staticmethod
    def format_winner_path(game_id: int, winner_id: int, winner_mention: str) -> str:
        """Форматирует путь победителя."""
        from app.database import get_kills_by_killer
        from app.messages import Messages

        winner_kills = get_kills_by_killer(game_id, winner_id)
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
                    killer=winner_mention,
                    victim=kill["victim_mention"],
                    location=kill["location_text"],
                    weapon=kill["weapon_text"],
                )
            )

        if winner_path_lines:
            return Messages.ASSASSIN_WINNER_PATH.format(kills="".join(winner_path_lines))
        return ""

    async def send_final_report(self, bot: "Bot", game_id: int, is_test: bool) -> None:
        """Отправляет финальный отчёт."""
        from app.database import get_game_by_id, get_player_by_id
        from app.messages import Messages

        game = get_game_by_id(game_id)
        if not game:
            return

        winner = get_player_by_id(game["winner_player_id"])
        if not winner:
            return

        chronology = self.format_kill_chronology(game_id)
        winner_path = self.format_winner_path(game_id, winner["id"], winner["mention_html"])

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

    async def send_death_announcement(
        self, bot: "Bot", game_id: int, victim: dict, is_test: bool
    ) -> None:
        """Отправляет анонс смерти."""
        from app.messages import Messages

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


# Singleton сервиса
knives_game_service = KnivesGameService()
