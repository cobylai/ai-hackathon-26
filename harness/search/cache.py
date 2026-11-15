"""A small SQLite cache of extracted page text, reused for 24 hours.

Keyed by URL. Only pages the browser read successfully are stored, so a cache
hit always means "this page was usable a moment ago". A broken or locked cache
never breaks a tool: reads and writes swallow their errors.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from harness import config

TTL_SECONDS = 24 * 60 * 60
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS pages ("
    "url TEXT PRIMARY KEY, text TEXT NOT NULL, fetched_at REAL NOT NULL)"
)


def db_path() -> Path:
    """`HARNESS_CACHE_DB` when set (tests), else ``~/.harness/cache.db``."""
    override = os.environ.get("HARNESS_CACHE_DB")
    return Path(override) if override else config.HOME_DIR / "cache.db"


def _now() -> float:
    """Wall clock, separate so tests can move it."""
    return time.time()


def _connect(path: str | os.PathLike | None = None) -> sqlite3.Connection:
    target = Path(path) if path is not None else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target, timeout=5)
    connection.execute(SCHEMA)
    connection.commit()
    return connection


def get(url: str, path: str | os.PathLike | None = None) -> str | None:
    """Extracted text for ``url`` if it was fetched less than a day ago."""
    if not url:
        return None
    try:
        connection = _connect(path)
        try:
            row = connection.execute(
                "SELECT text, fetched_at FROM pages WHERE url = ?", (url,)
            ).fetchone()
        finally:
            connection.close()
    except Exception:
        return None
    if not row:
        return None
    text, fetched_at = row
    if _now() - float(fetched_at) > TTL_SECONDS:
        return None
    return text


def put(url: str, text: str, path: str | os.PathLike | None = None) -> None:
    """Store text for ``url``, replacing an older copy."""
    if not url or not text or not text.strip():
        return
    try:
        connection = _connect(path)
        try:
            connection.execute(
                "INSERT OR REPLACE INTO pages (url, text, fetched_at) VALUES (?, ?, ?)",
                (url, text, _now()),
            )
            connection.commit()
        finally:
            connection.close()
    except Exception:
        pass


def clear(path: str | os.PathLike | None = None) -> None:
    """Drop every entry (tests)."""
    try:
        connection = _connect(path)
        try:
            connection.execute("DELETE FROM pages")
            connection.commit()
        finally:
            connection.close()
    except Exception:
        pass
