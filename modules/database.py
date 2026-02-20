"""
Database - SQLite cache and skill index (stdlib sqlite3, no external ORM)
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:

    def __init__(self, db_path: Path):
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(self._path), check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self.init_schema()
        logger.info("Database opened: %s", db_path)

    def close(self):
        if self._conn:
            self._conn.close()

    # ── Schema ────────────────────────────────────────────────────────────────

    def init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS github_cache (
                url        TEXT PRIMARY KEY,
                content    TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS search_results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                query       TEXT NOT NULL,
                owner       TEXT NOT NULL,
                repo        TEXT NOT NULL,
                skill_name  TEXT NOT NULL,
                description TEXT,
                url         TEXT,
                stars       INTEGER DEFAULT 0,
                cached_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_search_query
                ON search_results(query);

            CREATE TABLE IF NOT EXISTS skill_index (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                description   TEXT,
                scope         TEXT NOT NULL,
                path          TEXT NOT NULL,
                last_modified TEXT
            );
        """)
        self._conn.commit()

    # ── GitHub URL cache ─────────────────────────────────────────────────────

    def cache_get(self, url: str, max_age_hours: int = 24) -> str | None:
        """Return cached content string if fresh, else None."""
        row = self._conn.execute(
            "SELECT content, fetched_at FROM github_cache WHERE url = ?", (url,)
        ).fetchone()
        if not row:
            return None
        try:
            fetched = datetime.fromisoformat(row["fetched_at"])
            if datetime.utcnow() - fetched > timedelta(hours=max_age_hours):
                return None
        except Exception:
            return None
        return row["content"]

    def cache_set(self, url: str, content: str):
        self._conn.execute(
            "INSERT OR REPLACE INTO github_cache (url, content, fetched_at) VALUES (?, ?, ?)",
            (url, content, datetime.utcnow().isoformat()),
        )
        self._conn.commit()

    def cache_clear(self, url_prefix: str | None = None):
        if url_prefix:
            self._conn.execute(
                "DELETE FROM github_cache WHERE url LIKE ?", (url_prefix + "%",)
            )
        else:
            self._conn.execute("DELETE FROM github_cache")
        self._conn.commit()

    def cache_clear_expired(self, max_age_hours: int = 24):
        cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
        self._conn.execute("DELETE FROM github_cache WHERE fetched_at < ?", (cutoff,))
        self._conn.commit()

    # ── Search results cache ──────────────────────────────────────────────────

    def search_results_get(self, query: str, max_age_hours: int = 24) -> list[dict]:
        cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM search_results WHERE query = ? AND cached_at > ?",
            (query, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_results_set(self, query: str, results: list[dict]):
        self._conn.execute("DELETE FROM search_results WHERE query = ?", (query,))
        now = datetime.utcnow().isoformat()
        for r in results:
            self._conn.execute(
                "INSERT INTO search_results "
                "(query, owner, repo, skill_name, description, url, stars, cached_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    query,
                    r.get("owner", ""),
                    r.get("repo", ""),
                    r.get("skill_name", ""),
                    r.get("description", ""),
                    r.get("url", ""),
                    r.get("stars", 0),
                    now,
                ),
            )
        self._conn.commit()

    def search_results_clear(self):
        self._conn.execute("DELETE FROM search_results")
        self._conn.commit()
