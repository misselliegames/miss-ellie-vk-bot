from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class SessionStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self):
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @staticmethod
    def _serialize(session):
        payload = dict(session)
        payload["world_intros_sent"] = sorted(session.get("world_intros_sent", set()))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _deserialize(payload):
        session = json.loads(payload)
        session["world_intros_sent"] = set(session.get("world_intros_sent", []))
        session["option_orders"] = {
            int(question_id): order
            for question_id, order in session.get("option_orders", {}).items()
        }
        return session

    def save(self, user_id, session):
        payload = self._serialize(session)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO sessions (user_id, payload, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (int(user_id), payload),
            )

    def load_all(self):
        with self._connection() as connection:
            rows = connection.execute("SELECT user_id, payload FROM sessions").fetchall()
        return {int(user_id): self._deserialize(payload) for user_id, payload in rows}
