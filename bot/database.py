import sqlite3
from datetime import datetime, timezone
from typing import Any

from config import DATABASE_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                started_at TEXT NOT NULL,
                map_sent_at TEXT
            )
            """
        )
        conn.commit()


def upsert_user(
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, first_name, last_name, started_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name
            """,
            (user_id, username, first_name, last_name, now),
        )
        conn.commit()


def mark_map_sent(user_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET map_sent_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        conn.commit()


def has_received_map(user_id: int) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT map_sent_at FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return bool(row and row["map_sent_at"])


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()


def count_downloaders() -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE map_sent_at IS NOT NULL"
        ).fetchone()
    return int(row["cnt"]) if row else 0


def count_starters() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
    return int(row["cnt"]) if row else 0


def get_downloaders(limit: int, offset: int) -> list[sqlite3.Row]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM users
            WHERE map_sent_at IS NOT NULL
            ORDER BY map_sent_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return list(rows)


def get_all_users(limit: int, offset: int) -> list[sqlite3.Row]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM users
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return list(rows)


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)
