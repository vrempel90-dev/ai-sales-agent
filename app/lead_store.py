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
                    lead_score TEXT NOT NULL DEFAULT 'cold',
                    summary TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(leads)").fetchall()}
            migrations = {
                "last_name": "ALTER TABLE leads ADD COLUMN last_name TEXT",
                "lead_score": "ALTER TABLE leads ADD COLUMN lead_score TEXT NOT NULL DEFAULT 'cold'",
                "summary": "ALTER TABLE leads ADD COLUMN summary TEXT NOT NULL DEFAULT ''",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(statement)

    def record(self, user, message: str, stage: str, lead_score: str = "cold", summary: str = "") -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO leads (
                    user_id, username, first_name, last_name, last_message,
                    message_count, last_stage, lead_score, summary, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    last_message = excluded.last_message,
                    message_count = leads.message_count + 1,
                    last_stage = excluded.last_stage,
                    lead_score = excluded.lead_score,
                    summary = excluded.summary,
                    updated_at = excluded.updated_at
                """,
                (user.id, getattr(user, "username", None), getattr(user, "first_name", None), getattr(user, "last_name", None), message, stage, lead_score, summary, datetime.now(timezone.utc).isoformat()),
            )

    def last_summary(self) -> str:
        with self._connect() as connection:
            row = connection.execute("SELECT summary FROM leads ORDER BY updated_at DESC LIMIT 1").fetchone()
        return row["summary"] if row and row["summary"] else "нет сохранённых лидов"


class LeadConversationService:
    def __init__(self, database_path: str, enabled: bool):
        self.enabled = enabled
        self.store = LeadStore(database_path)
