from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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
    normalized_text: str | None = None
    hook: str | None = None
    content_angle: str | None = None
    content_format: str | None = None
    rubric: str | None = None
    goal: str | None = None
    niche: str | None = None
    cta_type: str | None = None
    hook_type: str | None = None
    pain_angle: str | None = None
    target_audience: str | None = None
    structure_type: str | None = None
    viral_score: int | None = None
    uniqueness_score: int | None = None
    quality_score: int | None = None
    hash: str | None = None
    semantic_key: str | None = None


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
                    error_reason TEXT,
                    normalized_text TEXT,
                    hook TEXT,
                    content_angle TEXT,
                    content_format TEXT,
                    rubric TEXT,
                    goal TEXT,
                    niche TEXT,
                    cta_type TEXT,
                    hook_type TEXT,
                    pain_angle TEXT,
                    target_audience TEXT,
                    structure_type TEXT,
                    viral_score INTEGER,
                    uniqueness_score INTEGER,
                    quality_score INTEGER,
                    hash TEXT,
                    semantic_key TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_posts_status ON threads_posts(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_posts_published_at ON threads_posts(published_at)")
            for column, definition in (("normalized_text", "TEXT"), ("hook", "TEXT"), ("content_angle", "TEXT"), ("content_format", "TEXT"), ("rubric", "TEXT"), ("goal", "TEXT"), ("niche", "TEXT"), ("cta_type", "TEXT"), ("hook_type", "TEXT"), ("pain_angle", "TEXT"), ("target_audience", "TEXT"), ("structure_type", "TEXT"), ("viral_score", "INTEGER"), ("uniqueness_score", "INTEGER"), ("quality_score", "INTEGER"), ("hash", "TEXT"), ("semantic_key", "TEXT")):
                existing = [row[1] for row in conn.execute("PRAGMA table_info(threads_posts)").fetchall()]
                if column not in existing:
                    conn.execute(f"ALTER TABLE threads_posts ADD COLUMN {column} {definition}")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS threads_duplicate_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    normalized_text TEXT,
                    hook TEXT,
                    skipped_at TEXT NOT NULL,
                    source TEXT,
                    post_id TEXT,
                    reason TEXT,
                    content_angle TEXT,
                    pain_angle TEXT,
                    cta_type TEXT,
                    structure_type TEXT,
                    hash TEXT,
                    semantic_key TEXT
                )
                """
            )
            existing_dup = [row[1] for row in conn.execute("PRAGMA table_info(threads_duplicate_events)").fetchall()]
            for column, definition in (("content_angle", "TEXT"), ("pain_angle", "TEXT"), ("cta_type", "TEXT"), ("structure_type", "TEXT"), ("hash", "TEXT"), ("semantic_key", "TEXT")):
                if column not in existing_dup:
                    conn.execute(f"ALTER TABLE threads_duplicate_events ADD COLUMN {column} {definition}")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_duplicate_events_skipped_at ON threads_duplicate_events(skipped_at)")

    def _row_to_post(self, row: sqlite3.Row | None) -> QueuedPost | None:
        if not row:
            return None
        data = dict(row)
        data.setdefault("normalized_text", None)
        data.setdefault("hook", None)
        for key in ("content_angle", "content_format", "rubric", "goal", "niche", "cta_type", "hook_type", "pain_angle", "target_audience", "structure_type", "viral_score", "uniqueness_score", "quality_score", "hash", "semantic_key"):
            data.setdefault(key, None)
        return QueuedPost(**data)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _text_fingerprints(self, text: str) -> tuple[str, str]:
        from app.threads_growth import extract_hook, normalize_thread_text

        return normalize_thread_text(text), extract_hook(text)

    def add_post(self, text: str, source: str = "manual", scheduled_hour: int | None = None, **metadata) -> QueuedPost:
        with self._connect() as conn:
            next_id = int(conn.execute("SELECT COALESCE(MAX(CAST(id AS INTEGER)), 0) + 1 FROM threads_posts WHERE id GLOB '[0-9]*'").fetchone()[0])
        from app.content_quality import build_metadata
        normalized_text, hook = self._text_fingerprints(text)
        quality_meta = build_metadata(text, **metadata)
        post = QueuedPost(str(next_id), text.strip(), "draft", self._now(), scheduled_hour=scheduled_hour, source=source, normalized_text=normalized_text, hook=quality_meta.hook or hook, content_angle=quality_meta.content_angle, content_format=quality_meta.content_format, rubric=metadata.get("rubric"), goal=metadata.get("goal"), niche=quality_meta.niche, cta_type=quality_meta.cta_type, hook_type=quality_meta.hook_type, pain_angle=quality_meta.pain_angle, target_audience=quality_meta.target_audience, structure_type=quality_meta.structure_type, viral_score=quality_meta.viral_score, uniqueness_score=quality_meta.uniqueness_score, quality_score=quality_meta.quality_score, hash=quality_meta.hash, semantic_key=quality_meta.semantic_key)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO threads_posts (id, text, status, created_at, scheduled_hour, source, normalized_text, hook, content_angle, content_format, rubric, goal, niche, cta_type, hook_type, pain_angle, target_audience, structure_type, viral_score, uniqueness_score, quality_score, hash, semantic_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (post.id, post.text, post.status, post.created_at, post.scheduled_hour, post.source, post.normalized_text, post.hook, post.content_angle, post.content_format, post.rubric, post.goal, post.niche, post.cta_type, post.hook_type, post.pain_angle, post.target_audience, post.structure_type, post.viral_score, post.uniqueness_score, post.quality_score, post.hash, post.semantic_key),
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

    def list_published_since(self, days: int = 7):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM threads_posts WHERE status = 'published' AND published_at >= ? ORDER BY published_at DESC",
                (cutoff,),
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def list_duplicate_guard_posts(self):
        published = self.list_published_since(7)
        active = [p for p in self.list_by_status("draft") + self.list_by_status("approved")]
        return active + published

    def find_duplicate_for_publish(self, id, text: str):
        from app.threads_growth import posts_are_duplicates

        for post in self.list_published_since(7):
            if str(post.id) != str(id) and posts_are_duplicates(text, post.text):
                return post
        return None

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

    def record_duplicate_skip(self, text: str, *, source: str | None = None, post_id: str | None = None, reason: str | None = None):
        from app.content_quality import build_metadata
        normalized_text, hook = self._text_fingerprints(text)
        meta = build_metadata(text)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO threads_duplicate_events (text, normalized_text, hook, skipped_at, source, post_id, reason, content_angle, pain_angle, cta_type, structure_type, hash, semantic_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (text.strip(), normalized_text, hook, self._now(), source, post_id, reason, meta.content_angle, meta.pain_angle, meta.cta_type, meta.structure_type, meta.hash, meta.semantic_key),
            )

    def mark_duplicate_skipped(self, id, *, duplicate_text: str | None = None, reason: str = "duplicate"):
        post = self.get_post(id)
        if post:
            self.record_duplicate_skip(duplicate_text or post.text, source=post.source, post_id=post.id, reason=reason)
        return self._set_status(id, "skipped", reason=reason)

    def list_content_history(self, days: int = 14, include_skipped: bool = True):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        statuses = "'draft','approved','published','failed','skipped'" if include_skipped else "'draft','approved','published'"
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM threads_posts
                WHERE status IN ({statuses})
                  AND (created_at >= ? OR published_at >= ?)
                ORDER BY COALESCE(published_at, created_at) DESC
                LIMIT 120
                """,
                (cutoff, cutoff),
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def get_duplicate_skipped_count_for_date(self, day: date) -> int:
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).isoformat()
        end = datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc).isoformat()
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM threads_duplicate_events WHERE skipped_at BETWEEN ? AND ?", (start, end)).fetchone()[0])

    def get_last_duplicate_skip(self):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM threads_duplicate_events ORDER BY skipped_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def get_next_draft(self):
        with self._connect() as conn:
            return self._row_to_post(conn.execute("SELECT * FROM threads_posts WHERE status = 'draft' ORDER BY created_at ASC LIMIT 1").fetchone())

    def get_next_publishable(self):
        with self._connect() as conn:
            return self._row_to_post(conn.execute("SELECT * FROM threads_posts WHERE status IN ('approved', 'draft') ORDER BY status = 'draft', created_at ASC LIMIT 1").fetchone())

    def update_post(self, id, text: str):
        from app.content_quality import build_metadata
        meta = build_metadata(text)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE threads_posts
                SET text = ?, status = 'draft', updated_at = ?, error_reason = NULL,
                    normalized_text = ?, hook = ?, content_angle = ?, content_format = ?, niche = ?, cta_type = ?,
                    hook_type = ?, pain_angle = ?, target_audience = ?, structure_type = ?,
                    viral_score = ?, uniqueness_score = ?, quality_score = ?, hash = ?, semantic_key = ?
                WHERE id = ?
                """,
                (text.strip(), self._now(), *self._text_fingerprints(text), meta.content_angle, meta.content_format, meta.niche, meta.cta_type, meta.hook_type, meta.pain_angle, meta.target_audience, meta.structure_type, meta.viral_score, meta.uniqueness_score, meta.quality_score, meta.hash, meta.semantic_key, str(id)),
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
