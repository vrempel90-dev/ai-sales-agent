from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import uuid4

TASK_STATUSES = {"pending", "running", "done", "failed", "blocked"}
TASK_TYPES = {"scan_threads", "comment_thread", "browser_test"}


@dataclass
class WorkerTask:
    task_id: str
    task_type: str
    keyword: str = ""
    thread_url: str = ""
    comment_text: str = ""
    score: int = 0
    status: str = "pending"
    result: str = ""
    error: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "WorkerTask":
        return cls(**{k: row[k] for k in row.keys()})


class ThreadsWorkerQueue:
    def __init__(self, database_path: str):
        self.database_path = database_path
        self.ensure_schema()

    def connect(self):
        con = sqlite3.connect(self.database_path)
        con.row_factory = sqlite3.Row
        return con

    def ensure_schema(self) -> None:
        with self.connect() as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS threads_worker_tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                keyword TEXT DEFAULT '',
                thread_url TEXT DEFAULT '',
                comment_text TEXT DEFAULT '',
                score INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT DEFAULT '',
                error TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
            )
            con.execute(
                """CREATE TABLE IF NOT EXISTS threads_worker_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_heartbeat TEXT DEFAULT '',
                last_error TEXT DEFAULT '',
                worker_connected INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT ''
            )"""
            )
            con.execute(
                "INSERT OR IGNORE INTO threads_worker_state(id,last_heartbeat,last_error,worker_connected,updated_at) VALUES(1,'','',0,'')"
            )

    def create_task(self, task_type: str, **fields: Any) -> WorkerTask:
        if task_type not in TASK_TYPES:
            raise ValueError(f"unsupported task_type: {task_type}")
        now = datetime.utcnow().isoformat()
        task = WorkerTask(
            task_id=fields.get("task_id") or uuid4().hex,
            task_type=task_type,
            keyword=fields.get("keyword", ""),
            thread_url=fields.get("thread_url", ""),
            comment_text=fields.get("comment_text", ""),
            score=int(fields.get("score", 0) or 0),
            status="pending",
            created_at=now,
            updated_at=now,
        )
        with self.connect() as con:
            con.execute(
                """INSERT INTO threads_worker_tasks(task_id,task_type,keyword,thread_url,comment_text,score,status,result,error,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (task.task_id, task.task_type, task.keyword, task.thread_url, task.comment_text, task.score, task.status, task.result, task.error, task.created_at, task.updated_at),
            )
        return task

    def claim_next(self) -> WorkerTask | None:
        now = datetime.utcnow().isoformat()
        with self.connect() as con:
            row = con.execute("SELECT * FROM threads_worker_tasks WHERE status='pending' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            con.execute("UPDATE threads_worker_tasks SET status='running', updated_at=? WHERE task_id=?", (now, row["task_id"]))
            row = con.execute("SELECT * FROM threads_worker_tasks WHERE task_id=?", (row["task_id"],)).fetchone()
            return WorkerTask.from_row(row)

    def update_task(self, task_id: str, status: str, result: dict[str, Any] | str = "", error: str = "", score: int | None = None) -> None:
        if status not in TASK_STATUSES:
            raise ValueError(f"unsupported status: {status}")
        result_text = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result or "")
        now = datetime.utcnow().isoformat()
        with self.connect() as con:
            if score is None:
                con.execute("UPDATE threads_worker_tasks SET status=?, result=?, error=?, updated_at=? WHERE task_id=?", (status, result_text, error, now, task_id))
            else:
                con.execute("UPDATE threads_worker_tasks SET status=?, result=?, error=?, score=?, updated_at=? WHERE task_id=?", (status, result_text, error, int(score), now, task_id))

    def heartbeat(self, error: str = "") -> None:
        now = datetime.utcnow().isoformat()
        with self.connect() as con:
            con.execute("UPDATE threads_worker_state SET last_heartbeat=?, last_error=COALESCE(NULLIF(?,''),last_error), worker_connected=1, updated_at=? WHERE id=1", (now, error, now))

    def status_summary(self) -> dict[str, Any]:
        today = date.today().isoformat() + "%"
        with self.connect() as con:
            state = con.execute("SELECT * FROM threads_worker_state WHERE id=1").fetchone()
            counts = {s: con.execute("SELECT COUNT(*) FROM threads_worker_tasks WHERE status=?", (s,)).fetchone()[0] for s in TASK_STATUSES}
            completed_today = con.execute("SELECT COUNT(*) FROM threads_worker_tasks WHERE status='done' AND updated_at LIKE ?", (today,)).fetchone()[0]
            failed_today = con.execute("SELECT COUNT(*) FROM threads_worker_tasks WHERE status IN ('failed','blocked') AND updated_at LIKE ?", (today,)).fetchone()[0]
        last_hb = state["last_heartbeat"] if state else ""
        connected = False
        if last_hb:
            try:
                connected = (datetime.utcnow() - datetime.fromisoformat(last_hb)).total_seconds() <= 120
            except ValueError:
                connected = False
        return {"worker_connected": connected, "pending": counts["pending"], "running": counts["running"], "completed_today": completed_today, "failed_today": failed_today, "last_worker_heartbeat": last_hb, "last_worker_error": state["last_error"] if state else ""}
