# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Code Style

Пиши код как сеньор с 10-летним стажем. Структура кода должна быть понятной и читаемой, все константы выноси в отдельный файл. При изменении функциональности обязательно обновляй документацию в README.md.

**Все константы централизованы:**
- `app/constants.py` — все технические константы (пути к медиа, координаты, лимиты)
- `app/messages.py` — все текстовые сообщения и эмодзи
- `app/callbacks.py` — идентификаторы callback-кнопок
- `.env` — конфигурация окружения (токены, ID, контент)

## Important Notes

**Игра "Достать ножи"** — основная игра бота, раньше называлась "Assassin". Всегда используй название "Достать ножи" в интерфейсе.

## Project Overview

Telegram bot for birthday party organization built with aiogram 3.x. Supports group chat commands, photo contests, beer pong team generation, polls, and Yandex Music playlist integration.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python run.py
```

## Architecture

### Router System

The bot uses aiogram's router system with three separate routers registered in specific order (see `app/handlers/__init__.py`):

1. `admin_router` — Admin commands in private chat (checked first)
2. `user_router` — Regular user commands in private chat
3. `group_router` — Group chat commands

Router order matters: admin router must be registered before user router to correctly filter admin vs regular users.

### Key Patterns

**Chat filtering:** Handlers use `F.chat.id == settings.bot.group_id` for group commands and `F.chat.type == ChatType.PRIVATE` combined with `F.from_user.id == ADMIN_ID` or `~(F.from_user.id == ADMIN_ID)` for private chat handlers.

**Callback data:** All callback identifiers are defined as constants in `app/callbacks.py` using prefix pattern (e.g., `menu:birthday`, `admin:photo_start`).

**FSM states:** Multi-step interactions use aiogram FSM. States are defined in `app/states.py`. Each state group handles one user flow (asking questions, creating polls, adding tracks, etc.).

**In-memory storage:** `app/storage.py` contains singleton storage classes for polls, photo contest entries, forwarded messages, and location. Data is lost on restart.

### Configuration

**Environment variables** (`.env` file via `app/config.py`):
- `BOT_TOKEN`, `ADMIN_ID`, `GROUP_ID` — required
- `BIRTHDAY_INFO`, `TRIP_INFO`, `WISHLIST_URL` — content configuration
- `YANDEX_MUSIC_TOKEN`, `YANDEX_PLAYLIST_KIND` — optional Yandex Music integration

**Constants** (`app/constants.py`):
- Media paths: `BIRTHDAY_PHOTO_1`, `BIRTHDAY_PHOTO_2`
- Geolocation: `TRIP_MEETING_POINT_LATITUDE`, `TRIP_MEETING_POINT_LONGITUDE`
- Limits: `MAX_PHOTO_CONTEST_PARTICIPANTS`, `MIN_TOURNAMENT_PARTICIPANTS`, etc.

### Text Management

All bot messages and button labels are centralized in `app/messages.py`:
- `Messages` class — all text responses
- `ButtonLabels` class — keyboard button text
- `Emojis` class — emoji constants

### External Services

`app/services/yandex_music.py` — Async Yandex Music API client with retry logic and rate limit handling. Extracts track IDs from URLs and adds tracks to configured playlist.

### Game "Достать ножи" (Get Knives Out)

`app/database.py` — SQLite database for persistent game storage (survives restarts):
- Tables: game, player, contract, kill_log, weapon, location
- All database operations use context managers with transactions

`app/handlers/spy_game.py` — Main game logic (600+ lines):
- Registration flow for real and virtual players
- Ring-based target assignment (circular kill chain)
- Death confirmation with two-step process
- Automatic target reassignment after kills
- Final report with chronology and winner's path
- Test mode with virtual players for debugging

**Key mechanics:**
- Safe zone: "курилка" (smoking area) - no kills allowed there
- Each player gets: target (another player) + weapon + location
- When target confirms death, killer gets target's target with new weapon/location
- Game ends when 1 player remains alive
- All announcements in test mode go to admin with 🧪 TEST prefix
