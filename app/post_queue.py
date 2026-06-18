from dataclasses import dataclass
from datetime import date, datetime, timezone
import os
import sqlite3

VALID_STATUSES = {"draft", "approved", "published", "skipped", "failed"}


@dataclass
class QueuedPost:
    id: str
    text: str
    status: str
    created_at: str
    updated_at: str | None = None
    published_at: str | None = None
    scheduled_hour: int | None = None
    source: str | None = None
    error_reason: str | None = None


class PostQueue:
    def __init__(self, database_path: str | None = None):
        self.database_path = database_path or os.getenv("DATABASE_PATH", "./ai_sales_agent.db")
        self._ensure_database_dir()
        self._init_db()

    def _ensure_database_dir(self) -> None:
        directory = os.path.dirname(os.path.abspath(self.database_path))
        if directory:
            os.makedirs(directory, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS threads_posts (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    published_at TEXT,
                    scheduled_hour INTEGER,
                    source TEXT,
                    error_reason TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_posts_status ON threads_posts(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_posts_published_at ON threads_posts(published_at)")

    def _row_to_post(self, row: sqlite3.Row | None) -> QueuedPost | None:
        return QueuedPost(**dict(row)) if row else None

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_post(self, text: str, source: str = "manual", scheduled_hour: int | None = None) -> QueuedPost:
        with self._connect() as conn:
            next_id = int(conn.execute("SELECT COALESCE(MAX(CAST(id AS INTEGER)), 0) + 1 FROM threads_posts WHERE id GLOB '[0-9]*'").fetchone()[0])
        post = QueuedPost(str(next_id), text.strip(), "draft", self._now(), scheduled_hour=scheduled_hour, source=source)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO threads_posts (id, text, status, created_at, scheduled_hour, source) VALUES (?, ?, ?, ?, ?, ?)",
                (post.id, post.text, post.status, post.created_at, post.scheduled_hour, post.source),
            )
        return post

    def get_post(self, id):
        with self._connect() as conn:
            return self._row_to_post(conn.execute("SELECT * FROM threads_posts WHERE id = ?", (str(id),)).fetchone())

    def list_posts(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM threads_posts ORDER BY created_at ASC").fetchall()
        return [self._row_to_post(row) for row in rows]

    def list_by_status(self, status: str):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM threads_posts WHERE status = ? ORDER BY created_at ASC", (status,)).fetchall()
        return [self._row_to_post(row) for row in rows]

    def list_publishable(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM threads_posts WHERE status IN ('approved', 'draft') ORDER BY created_at ASC"
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def list_active_and_published_today(self):
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).isoformat()
        end = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM threads_posts
                WHERE status IN ('draft', 'approved')
                   OR (status = 'published' AND published_at BETWEEN ? AND ?)
                ORDER BY created_at ASC
                """,
                (start, end),
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def _set_status(self, id, status: str, *, published: bool = False, reason: str | None = None):
        if status not in VALID_STATUSES:
            raise ValueError(f"Unknown post status: {status}")
        now = self._now()
        published_at = now if published else None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE threads_posts
                SET status = ?, updated_at = ?, published_at = COALESCE(?, published_at), error_reason = ?
                WHERE id = ?
                """,
                (status, now, published_at, reason, str(id)),
            )
        return self.get_post(id)

    def approve_post(self, id): return self._set_status(id, "approved")
    def skip_post(self, id): return self._set_status(id, "skipped")
    def mark_published(self, id): return self._set_status(id, "published", published=True)
    def mark_failed(self, id, reason): return self._set_status(id, "failed", reason=reason)

    def get_next_draft(self):
        with self._connect() as conn:
            return self._row_to_post(conn.execute("SELECT * FROM threads_posts WHERE status = 'draft' ORDER BY created_at ASC LIMIT 1").fetchone())

    def get_next_publishable(self):
        with self._connect() as conn:
            return self._row_to_post(conn.execute("SELECT * FROM threads_posts WHERE status IN ('approved', 'draft') ORDER BY status = 'draft', created_at ASC LIMIT 1").fetchone())

    def update_post(self, id, text: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE threads_posts SET text = ?, status = 'draft', updated_at = ?, error_reason = NULL WHERE id = ?",
                (text.strip(), self._now(), str(id)),
            )
        return self.get_post(id)

    def get_draft_count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM threads_posts WHERE status = 'draft'").fetchone()[0])

    def get_published_count_for_date(self, day: date) -> int:
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).isoformat()
        end = datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc).isoformat()
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM threads_posts WHERE status = 'published' AND published_at BETWEEN ? AND ?", (start, end)).fetchone()[0])


post_queue = PostQueue()
