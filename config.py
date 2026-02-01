import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
GROUP_ID = os.getenv("GROUP_ID")

BIRTHDAY_INFO = os.getenv("BIRTHDAY_INFO", "Информация о дне рождения не настроена")
TRIP_INFO = os.getenv("TRIP_INFO", "Информация о выезде не настроена")
WISHLIST_URL = os.getenv("WISHLIST_URL", "Ссылка на вишлист не настроена")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env файле")

if not ADMIN_ID:
    raise ValueError("ADMIN_ID не установлен в .env файле")

if not GROUP_ID:
    raise ValueError("GROUP_ID не установлен в .env файле")

# Преобразуем в int для сравнения
ADMIN_ID = int(ADMIN_ID)
GROUP_ID = int(GROUP_ID)
