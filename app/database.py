"""
База данных для игры "Достать ножи".

Использует SQLite для персистентного хранения состояния игры.
Все операции транзакционные, база переживает перезапуски бота.

Структура:
- game: информация об играх (статус, тестовый режим, победитель)
- player: игроки (реальные и виртуальные с TG ID и упоминаниями)
- contract: активные задания (убийца → цель + оружие + локация)
- kill_log: история убийств с временными метками
- weapon: список доступных оружий
- location: список доступных локаций для убийств

Все timestamp поля автоматически конвертируются в datetime объекты
благодаря sqlite3.PARSE_DECLTYPES.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "assassin_game.db"


@contextmanager
def get_db():
    """Контекстный менеджер для работы с БД."""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except sqlite3.DatabaseError as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    except Exception as e:
        conn.rollback()
        logger.exception(f"Unexpected error: {e}")
        raise
    finally:
        conn.close()


def init_database() -> None:
    """Инициализация базы данных."""
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS game (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL DEFAULT 'draft',
                is_test_mode BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                winner_player_id INTEGER,
                group_chat_id INTEGER NOT NULL,
                FOREIGN KEY (winner_player_id) REFERENCES player(id)
            );

            CREATE TABLE IF NOT EXISTS player (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                tg_user_id INTEGER,
                is_virtual BOOLEAN NOT NULL DEFAULT 0,
                display_name TEXT NOT NULL,
                username TEXT,
                mention_html TEXT NOT NULL,
                is_alive BOOLEAN NOT NULL DEFAULT 1,
                registered_at TIMESTAMP NOT NULL,
                died_at TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES game(id)
            );

            CREATE TABLE IF NOT EXISTS contract (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                assassin_player_id INTEGER NOT NULL,
                target_player_id INTEGER NOT NULL,
                weapon_text TEXT NOT NULL,
                location_text TEXT NOT NULL,
                assigned_at TIMESTAMP NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                FOREIGN KEY (game_id) REFERENCES game(id),
                FOREIGN KEY (assassin_player_id) REFERENCES player(id),
                FOREIGN KEY (target_player_id) REFERENCES player(id)
            );

            CREATE TABLE IF NOT EXISTS kill_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                killer_player_id INTEGER NOT NULL,
                victim_player_id INTEGER NOT NULL,
                weapon_text TEXT NOT NULL,
                location_text TEXT NOT NULL,
                killed_at TIMESTAMP NOT NULL,
                is_test BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY (game_id) REFERENCES game(id),
                FOREIGN KEY (killer_player_id) REFERENCES player(id),
                FOREIGN KEY (victim_player_id) REFERENCES player(id)
            );

            CREATE TABLE IF NOT EXISTS weapon (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL UNIQUE,
                is_active BOOLEAN NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS location (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL UNIQUE,
                is_active BOOLEAN NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_game_status ON game(status);
            CREATE INDEX IF NOT EXISTS idx_player_game ON player(game_id);
            CREATE INDEX IF NOT EXISTS idx_player_tg_user ON player(tg_user_id);
            CREATE INDEX IF NOT EXISTS idx_contract_active ON contract(is_active);
            CREATE INDEX IF NOT EXISTS idx_contract_game ON contract(game_id);
            """
        )


# === Game ===


def create_game(is_test_mode: bool, group_chat_id: int) -> int:
    """Создать новую игру."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO game (status, is_test_mode, created_at, group_chat_id)
            VALUES ('registration', ?, ?, ?)
            """,
            (is_test_mode, datetime.now(), group_chat_id),
        )
        return cursor.lastrowid


def get_active_game() -> Optional[sqlite3.Row]:
    """Получить активную игру (не finished)."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM game
            WHERE status IN ('registration', 'running')
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        return cursor.fetchone()


def get_game_by_id(game_id: int) -> Optional[sqlite3.Row]:
    """Получить игру по ID."""
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM game WHERE id = ?", (game_id,))
        return cursor.fetchone()


def update_game_status(game_id: int, status: str, **kwargs) -> None:
    """Обновить статус игры."""
    fields = ["status = ?"]
    values = [status]

    if "started_at" in kwargs:
        fields.append("started_at = ?")
        values.append(kwargs["started_at"])

    if "finished_at" in kwargs:
        fields.append("finished_at = ?")
        values.append(kwargs["finished_at"])

    if "winner_player_id" in kwargs:
        fields.append("winner_player_id = ?")
        values.append(kwargs["winner_player_id"])

    values.append(game_id)

    with get_db() as conn:
        conn.execute(
            f"UPDATE game SET {', '.join(fields)} WHERE id = ?", tuple(values)
        )


# === Player ===


def create_player(
    game_id: int,
    display_name: str,
    mention_html: str,
    tg_user_id: Optional[int] = None,
    username: Optional[str] = None,
    is_virtual: bool = False,
) -> int:
    """Создать игрока."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO player (
                game_id, tg_user_id, is_virtual, display_name,
                username, mention_html, registered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                tg_user_id,
                is_virtual,
                display_name,
                username,
                mention_html,
                datetime.now(),
            ),
        )
        return cursor.lastrowid


def get_player_by_tg_id(game_id: int, tg_user_id: int) -> Optional[sqlite3.Row]:
    """Найти игрока по Telegram ID."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM player
            WHERE game_id = ? AND tg_user_id = ?
            """,
            (game_id, tg_user_id),
        )
        return cursor.fetchone()


def get_player_by_id(player_id: int) -> Optional[sqlite3.Row]:
    """Получить игрока по ID."""
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM player WHERE id = ?", (player_id,))
        return cursor.fetchone()


def get_all_players(game_id: int) -> List[sqlite3.Row]:
    """Получить всех игроков игры."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM player
            WHERE game_id = ?
            ORDER BY registered_at
            """,
            (game_id,),
        )
        return cursor.fetchall()


def get_alive_players(game_id: int) -> List[sqlite3.Row]:
    """Получить живых игроков."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM player
            WHERE game_id = ? AND is_alive = 1
            ORDER BY registered_at
            """,
            (game_id,),
        )
        return cursor.fetchall()


def mark_player_dead(player_id: int) -> None:
    """Пометить игрока мёртвым."""
    with get_db() as conn:
        conn.execute(
            """
            UPDATE player
            SET is_alive = 0, died_at = ?
            WHERE id = ?
            """,
            (datetime.now(), player_id),
        )


def count_players(game_id: int) -> int:
    """Подсчитать количество игроков."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM player WHERE game_id = ?", (game_id,)
        )
        return cursor.fetchone()[0]


# === Contract ===


def create_contract(
    game_id: int,
    assassin_id: int,
    target_id: int,
    weapon: str,
    location: str,
) -> int:
    """Создать контракт."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO contract (
                game_id, assassin_player_id, target_player_id,
                weapon_text, location_text, assigned_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (game_id, assassin_id, target_id, weapon, location, datetime.now()),
        )
        return cursor.lastrowid


def get_active_contract_for_assassin(
    game_id: int, assassin_id: int
) -> Optional[sqlite3.Row]:
    """Получить активный контракт убийцы."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM contract
            WHERE game_id = ? AND assassin_player_id = ? AND is_active = 1
            """,
            (game_id, assassin_id),
        )
        return cursor.fetchone()


def get_active_contract_for_target(
    game_id: int, target_id: int
) -> Optional[sqlite3.Row]:
    """Получить активный контракт на жертву (кто должен её убить)."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM contract
            WHERE game_id = ? AND target_player_id = ? AND is_active = 1
            """,
            (game_id, target_id),
        )
        return cursor.fetchone()


def deactivate_contract(contract_id: int) -> None:
    """Деактивировать контракт."""
    with get_db() as conn:
        conn.execute(
            "UPDATE contract SET is_active = 0 WHERE id = ?", (contract_id,)
        )


# === KillLog ===


def create_kill_log(
    game_id: int,
    killer_id: int,
    victim_id: int,
    weapon: str,
    location: str,
    is_test: bool,
) -> int:
    """Создать запись об убийстве."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO kill_log (
                game_id, killer_player_id, victim_player_id,
                weapon_text, location_text, killed_at, is_test
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (game_id, killer_id, victim_id, weapon, location, datetime.now(), is_test),
        )
        return cursor.lastrowid


def get_all_kills(game_id: int) -> List[sqlite3.Row]:
    """Получить все убийства в хронологическом порядке."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT kl.*,
                   k.display_name as killer_name, k.mention_html as killer_mention,
                   v.display_name as victim_name, v.mention_html as victim_mention
            FROM kill_log kl
            JOIN player k ON kl.killer_player_id = k.id
            JOIN player v ON kl.victim_player_id = v.id
            WHERE kl.game_id = ?
            ORDER BY kl.killed_at
            """,
            (game_id,),
        )
        return cursor.fetchall()


def get_kills_by_killer(game_id: int, killer_id: int) -> List[sqlite3.Row]:
    """Получить убийства конкретного игрока."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT kl.*,
                   v.display_name as victim_name, v.mention_html as victim_mention
            FROM kill_log kl
            JOIN player v ON kl.victim_player_id = v.id
            WHERE kl.game_id = ? AND kl.killer_player_id = ?
            ORDER BY kl.killed_at
            """,
            (game_id, killer_id),
        )
        return cursor.fetchall()


# === Weapon ===


def add_weapon(text: str) -> int:
    """Добавить оружие."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO weapon (text) VALUES (?)", (text,)
        )
        if cursor.rowcount == 0:
            cursor = conn.execute("SELECT id FROM weapon WHERE text = ?", (text,))
            return cursor.fetchone()[0]
        return cursor.lastrowid


def get_active_weapons() -> List[str]:
    """Получить список активных оружий."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT text FROM weapon WHERE is_active = 1 ORDER BY id"
        )
        return [row[0] for row in cursor.fetchall()]


def clear_weapons() -> None:
    """Очистить все оружия."""
    with get_db() as conn:
        conn.execute("DELETE FROM weapon")


def get_all_weapons() -> List[Tuple[int, str, bool]]:
    """Получить все оружия."""
    with get_db() as conn:
        cursor = conn.execute("SELECT id, text, is_active FROM weapon ORDER BY id")
        return cursor.fetchall()


# === Location ===


def add_location(text: str) -> int:
    """Добавить локацию."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO location (text) VALUES (?)", (text,)
        )
        if cursor.rowcount == 0:
            cursor = conn.execute("SELECT id FROM location WHERE text = ?", (text,))
            return cursor.fetchone()[0]
        return cursor.lastrowid


def get_active_locations() -> List[str]:
    """Получить список активных локаций."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT text FROM location WHERE is_active = 1 ORDER BY id"
        )
        return [row[0] for row in cursor.fetchall()]


def clear_locations() -> None:
    """Очистить все локации."""
    with get_db() as conn:
        conn.execute("DELETE FROM location")


def get_all_locations() -> List[Tuple[int, str, bool]]:
    """Получить все локации."""
    with get_db() as conn:
        cursor = conn.execute("SELECT id, text, is_active FROM location ORDER BY id")
        return cursor.fetchall()
