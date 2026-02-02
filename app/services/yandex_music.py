"""
Сервис для работы с Яндекс Музыкой.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional

from yandex_music import ClientAsync
from yandex_music.exceptions import NetworkError

from app.config import settings
from app.constants import YANDEX_MUSIC_URL_PATTERN

logger = logging.getLogger(__name__)

# Паттерн для извлечения track_id из URL (с группой захвата для последней цифровой группы)
YANDEX_MUSIC_PATTERN = re.compile(r'music\.yandex\.(?:ru|com)/album/\d+/track/(\d+)')

# Настройки retry
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 5
REQUEST_TIMEOUT = 30


@dataclass
class TrackInfo:
    """Информация о треке."""

    track_id: str
    title: str
    artists: str
    album_id: int


class YandexMusicService:
    """Сервис для работы с Яндекс Музыкой."""

    def __init__(self) -> None:
        self._client: Optional[ClientAsync] = None

    @property
    def is_configured(self) -> bool:
        return settings.yandex_music.is_configured

    async def _get_client(self) -> Optional[ClientAsync]:
        """Ленивая инициализация клиента."""
        if self._client is not None:
            return self._client

        if not self.is_configured:
            logger.warning("YANDEX_MUSIC_TOKEN не установлен")
            return None

        for attempt in range(MAX_RETRIES):
            try:
                client = ClientAsync(settings.yandex_music.token)
                client.request.set_timeout(REQUEST_TIMEOUT)
                self._client = await client.init()
                logger.info("Яндекс Музыка клиент инициализирован")
                return self._client
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}/{MAX_RETRIES} инициализации YM: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2)

        logger.error("Не удалось инициализировать Яндекс Музыку")
        return None

    @staticmethod
    def extract_track_id(url: str) -> Optional[str]:
        """Извлекает track_id из ссылки на Яндекс Музыку."""
        match = YANDEX_MUSIC_PATTERN.search(url)
        return match.group(1) if match else None

    async def get_track_info(self, track_id: str) -> Optional[TrackInfo]:
        """Получает информацию о треке."""
        client = await self._get_client()
        if not client:
            return None

        try:
            tracks = await client.tracks([track_id])
            if not tracks:
                return None

            track = tracks[0]
            artists = ", ".join([a.name for a in track.artists]) if track.artists else "Неизвестный исполнитель"
            album_id = track.albums[0].id if track.albums else 0

            return TrackInfo(
                track_id=track_id,
                title=track.title,
                artists=artists,
                album_id=album_id,
            )
        except Exception as e:
            logger.error(f"Ошибка получения трека: {e}")
            return None

    async def add_track_to_playlist(self, track_id: str) -> tuple[bool, str, Optional[TrackInfo]]:
        """
        Добавляет трек в плейлист.

        Returns:
            tuple: (success, error_message, track_info)
        """
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(MAX_RETRIES):
            try:
                client = await self._get_client()
                if not client:
                    return False, "connection_error", None

                # Получаем информацию о треке
                track_info = await self.get_track_info(track_id)
                if not track_info:
                    return False, "track_not_found", None

                # Получаем информацию о пользователе
                user_id = client.me.account.uid

                # Получаем текущий плейлист для revision
                playlist = await client.users_playlists(
                    int(settings.yandex_music.playlist_kind),
                    user_id
                )
                if not playlist:
                    return False, "playlist_not_found", None

                # Добавляем трек в плейлист
                await client.users_playlists_insert_track(
                    kind=int(settings.yandex_music.playlist_kind),
                    track_id=track_id,
                    album_id=track_info.album_id,
                    revision=playlist.revision,
                    user_id=user_id
                )

                return True, "", track_info

            except NetworkError as e:
                error_str = str(e)
                if "429" in error_str:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(
                            f"Rate limit (429), попытка {attempt + 1}/{MAX_RETRIES}, "
                            f"ждём {retry_delay} сек..."
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    return False, "rate_limit", None
                logger.error(f"Ошибка сети: {error_str[:100]}")
                return False, "network_error", None

            except Exception as e:
                logger.error(f"Ошибка при добавлении трека: {e}", exc_info=True)
                return False, "unexpected_error", None

        return False, "max_retries", None


# Singleton сервиса
yandex_music_service = YandexMusicService()
