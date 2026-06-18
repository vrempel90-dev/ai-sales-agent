from datetime import datetime, timezone
import os
import sqlite3


class LeadStore:
    def __init__(self, database_path: str):
        self.database_path = database_path
        directory = os.path.dirname(os.path.abspath(database_path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    last_message TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 1,
                    last_stage TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(leads)").fetchall()
            }
            if "last_name" not in columns:
                connection.execute("ALTER TABLE leads ADD COLUMN last_name TEXT")

    def record(self, user, message: str, stage: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO leads (
                    user_id, username, first_name, last_name, last_message,
                    message_count, last_stage, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    last_message = excluded.last_message,
                    message_count = leads.message_count + 1,
                    last_stage = excluded.last_stage,
                    updated_at = excluded.updated_at
                """,
                (
                    user.id,
                    getattr(user, "username", None),
                    getattr(user, "first_name", None),
                    getattr(user, "last_name", None),
                    message,
                    stage,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )


class LeadConversationService:
    def __init__(self, database_path: str, enabled: bool):
        self.enabled = enabled
        self.store = LeadStore(database_path)
