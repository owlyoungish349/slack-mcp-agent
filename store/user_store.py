"""Persistent SQLite store for Threshold: user language preferences and impact events.

The database file lives at THRESHOLD_DATA_DIR/threshold.db.
Set THRESHOLD_DATA_DIR to the droplet bind-mount path (/data) in production so
metrics survive container restarts and deploys.
"""

import json
import os
import sqlite3
import threading
from pathlib import Path

_DATA_DIR = Path(os.environ.get("THRESHOLD_DATA_DIR", "./data"))
_lock = threading.Lock()


def _db_path() -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR / "threshold.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Call once at app startup."""
    with _lock, _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id      TEXT PRIMARY KEY,
                language     TEXT NOT NULL DEFAULT 'en',
                language_name TEXT NOT NULL DEFAULT 'English',
                opted_in_digest INTEGER NOT NULL DEFAULT 1,
                created_at   TEXT DEFAULT (datetime('now')),
                updated_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS events (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type   TEXT NOT NULL,
                user_id      TEXT,
                language     TEXT,
                metadata     TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            );
        """)


# ── Language preferences ────────────────────────────────────────────────────


def get_language(user_id: str) -> tuple[str, str]:
    """Return (language_code, language_name). Defaults to ('en', 'English')."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT language, language_name FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return (row["language"], row["language_name"]) if row else ("en", "English")


def set_language(user_id: str, language: str, language_name: str) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (user_id, language, language_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                language      = excluded.language,
                language_name = excluded.language_name,
                updated_at    = datetime('now')
            """,
            (user_id, language, language_name),
        )


def get_opted_in_users() -> list[str]:
    """Return user IDs of everyone who has opted in to the digest."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT user_id FROM user_preferences WHERE opted_in_digest = 1"
        ).fetchall()
    return [r["user_id"] for r in rows]


# ── Impact events ───────────────────────────────────────────────────────────


def log_event(
    event_type: str,
    user_id: str | None = None,
    language: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Log a Threshold impact event.

    event_type values: welcomed, language_set, matched, intro_made, digest_sent
    """
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO events (event_type, user_id, language, metadata) VALUES (?, ?, ?, ?)",
            (event_type, user_id, language, json.dumps(metadata) if metadata else None),
        )


def was_welcomed(user_id: str) -> bool:
    """True if this user has already received a welcome DM."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM events WHERE event_type = 'welcomed' AND user_id = ?",
            (user_id,),
        ).fetchone()
    return row is not None


def get_impact_summary() -> dict:
    """Return aggregated impact metrics for the /threshold-impact command."""
    with _connect() as conn:

        def count_events(etype: str) -> int:
            return conn.execute(
                "SELECT COUNT(*) FROM events WHERE event_type = ?", (etype,)
            ).fetchone()[0]

        def count_people(etype: str) -> int:
            return conn.execute(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM events
                WHERE event_type = ? AND user_id IS NOT NULL
                """,
                (etype,),
            ).fetchone()[0]

        # Welcome and match cards may be re-run during a conversation or demo;
        # the dashboard should represent people helped rather than attempts.
        welcomed = count_people("welcomed")
        matched = count_people("matched")

        # These are delivered actions, so retain their event counts.
        intro_made = count_events("intro_made")
        digest_sent = count_events("digest_sent")

        lang_rows = conn.execute(
            "SELECT DISTINCT language FROM user_preferences WHERE language IS NOT NULL"
        ).fetchall()
        languages_served = [r["language"] for r in lang_rows]

        avg_seconds = _calc_avg_connection_time(conn)

    return {
        "welcomed": welcomed,
        "matched": matched,
        "intro_made": intro_made,
        "digest_sent": digest_sent,
        "languages_served": languages_served,
        "referrals_needed": 0,
        "avg_connection_seconds": avg_seconds,
    }


def _calc_avg_connection_time(conn: sqlite3.Connection) -> float | None:
    """Seconds from first 'welcomed' to first 'intro_made' per user, averaged."""
    try:
        rows = conn.execute("""
            SELECT w.user_id,
                   MIN(w.created_at) AS welcome_time,
                   MIN(i.created_at) AS intro_time
            FROM   events w
            JOIN   events i
                   ON w.user_id = i.user_id AND i.event_type = 'intro_made'
            WHERE  w.event_type = 'welcomed'
            GROUP  BY w.user_id
        """).fetchall()
        if not rows:
            return None
        from datetime import datetime

        diffs = []
        fmt = "%Y-%m-%d %H:%M:%S"
        for r in rows:
            try:
                wt = datetime.strptime(r["welcome_time"], fmt)
                it = datetime.strptime(r["intro_time"], fmt)
                diffs.append((it - wt).total_seconds())
            except Exception:
                pass
        return sum(diffs) / len(diffs) if diffs else None
    except Exception:
        return None
