"""
Конфигурация приложения.
Загружает переменные окружения и валидирует их.
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class BotConfig:
    """Основная конфигурация бота."""

    token: str
    admin_id: int
    group_id: int


@dataclass(frozen=True)
class ContentConfig:
    """Контент для отображения пользователям."""

    birthday_info: str
    trip_info: str
    wishlist_url: str


@dataclass(frozen=True)
class YandexMusicConfig:
    """Конфигурация Яндекс Музыки."""

    token: Optional[str]
    playlist_kind: Optional[str]

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.playlist_kind)


@dataclass(frozen=True)
class Settings:
    """Все настройки приложения."""

    bot: BotConfig
    content: ContentConfig
    yandex_music: YandexMusicConfig


def load_settings() -> Settings:
    """Загружает и валидирует настройки из переменных окружения."""
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN")
    admin_id = os.getenv("ADMIN_ID")
    group_id = os.getenv("GROUP_ID")

    if not bot_token:
        raise ValueError("BOT_TOKEN не установлен в .env файле")
    if not admin_id:
        raise ValueError("ADMIN_ID не установлен в .env файле")
    if not group_id:
        raise ValueError("GROUP_ID не установлен в .env файле")

    return Settings(
        bot=BotConfig(
            token=bot_token,
            admin_id=int(admin_id),
            group_id=int(group_id),
        ),
        content=ContentConfig(
            birthday_info=os.getenv("BIRTHDAY_INFO", "Информация о дне рождения не настроена"),
            trip_info=os.getenv("TRIP_INFO", "Информация о выезде не настроена"),
            wishlist_url=os.getenv("WISHLIST_URL", "Ссылка на вишлист не настроена"),
        ),
        yandex_music=YandexMusicConfig(
            token=os.getenv("YANDEX_MUSIC_TOKEN"),
            playlist_kind=os.getenv("YANDEX_PLAYLIST_KIND"),
        ),
    )


# Singleton для настроек
settings = load_settings()
