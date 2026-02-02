"""
Общие константы приложения.
"""

# Regex паттерн для ссылок Яндекс Музыки (для использования в F.text.regexp)
YANDEX_MUSIC_URL_PATTERN = r'music\.yandex\.(ru|com)/album/\d+/track/\d+'

# Турнир
MIN_TOURNAMENT_PARTICIPANTS = 4
MAX_TOURNAMENT_PARTICIPANTS = 64  # 6 раундов максимум
TOURNAMENT_TEAM_SIZE_THRESHOLD = 11  # До 11 - команды по 2, выше - по 3

# Фото-конкурс
MAX_PHOTO_CONTEST_PARTICIPANTS = 22
