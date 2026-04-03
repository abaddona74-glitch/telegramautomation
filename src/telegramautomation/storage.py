from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class SendWindow:
    window_start: datetime
    sent_count: int


class SQLiteStateStore:
    def __init__(self, path: str) -> None:
        self._path = path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS send_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    row_id TEXT NOT NULL,
                    sent_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def register_send(self, row_id: str, sent_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO send_events(row_id, sent_at) VALUES(?, ?)",
                (row_id, sent_at.isoformat()),
            )
            conn.commit()

    def count_sent_in_window(self, hours: int, now_utc: datetime) -> int:
        window_start = now_utc - timedelta(hours=hours)
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT COUNT(1) FROM send_events WHERE sent_at >= ?",
                (window_start.isoformat(),),
            )
            row = cursor.fetchone()
        return int(row[0] if row else 0)

    def prune_old_events(self, older_than_hours: int = 24 * 30) -> None:
        threshold = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        with self._connect() as conn:
            conn.execute("DELETE FROM send_events WHERE sent_at < ?", (threshold.isoformat(),))
            conn.commit()
