# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Code Style

Пиши код как сеньор с 10-летним стажем. Структура кода должна быть понятной и читаемой, все константы выноси в отдельный файл. При изменении функциональности обязательно обновляй документацию в README.md.

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

All settings loaded from environment variables via `app/config.py`:
- `BOT_TOKEN`, `ADMIN_ID`, `GROUP_ID` — required
- `BIRTHDAY_INFO`, `TRIP_INFO`, `WISHLIST_URL` — content configuration
- `YANDEX_MUSIC_TOKEN`, `YANDEX_PLAYLIST_KIND` — optional Yandex Music integration

### Text Management

All bot messages and button labels are centralized in `app/messages.py`:
- `Messages` class — all text responses
- `ButtonLabels` class — keyboard button text
- `Emojis` class — emoji constants

### External Services

`app/services/yandex_music.py` — Async Yandex Music API client with retry logic and rate limit handling. Extracts track IDs from URLs and adds tracks to configured playlist.
