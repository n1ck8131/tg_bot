"""
Конфигурация (для обратной совместимости).
Рекомендуется использовать: from app.config import settings
"""

from app.config import settings

# Экспорт для обратной совместимости
BOT_TOKEN = settings.bot.token
ADMIN_ID = settings.bot.admin_id
GROUP_ID = settings.bot.group_id

BIRTHDAY_INFO = settings.content.birthday_info
TRIP_INFO = settings.content.trip_info
WISHLIST_URL = settings.content.wishlist_url

YANDEX_MUSIC_TOKEN = settings.yandex_music.token
YANDEX_PLAYLIST_KIND = settings.yandex_music.playlist_kind
