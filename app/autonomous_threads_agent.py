from __future__ import annotations

import asyncio
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.threads_browser_layer import ThreadsBrowserLayer, duplicate_guard, semantic_key
from app.threads_worker_client import ThreadsWorkerQueue

BLOCKING_STATES = {"captcha", "checkpoint", "rate_limit", "action_blocked", "login_issue", "suspicious_activity", "session_expired", "interface_changed"}
KEYWORDS = [
    "салон красоты", "маникюр", "косметолог", "стоматология", "клиника", "барбершоп",
    "запись в директ", "заявки", "администратор", "клиент не отвечает", "директ",
    "WhatsApp", "бизнес", "услуги", "CRM", "Алматы", "Казахстан",
]
TRASH_WORDS = {"политика", "мем", "мемы", "знакомства", "токсично", "война", "скандал"}
BUSINESS_WORDS = {"бизнес", "услуг", "запись", "direct", "директ", "whatsapp", "telegram", "crm", "админ", "заяв"}

@dataclass
class AgentActionResult:
    published_comment: bool = False
    sent_dm: bool = False
    comment_prepared: bool = False
    dm_prepared: bool = False
    skipped_reason: str = ""
    score: int = 0

class ThreadsBrowserAgent:
    """Optional browser layer. Base implementation is honest dry-run/no-browser."""
    configured = False

    def find_threads(self, limit: int = 30):
        sample = "Салон красоты бизнес услуги запись в Алматы теряет заявки: клиенты пишут в Direct и WhatsApp Telegram, администратор отвечает поздно, CRM нет"
        return [{"id": "dry-thread-1", "text": sample, "profile_id": "beauty-almaty", "dm_open": True}][:limit]
    def open_thread(self, thread_id: str): return {"id": thread_id}
    def read_thread_context(self, thread): return thread.get("text", "")
    def score_thread(self, text: str): return score_thread_text(text)
    def generate_comment(self, text: str): return generate_comment_text(text)
    def publish_comment(self, thread, comment: str): return False, "Browser mode is not configured"
    def open_profile(self, profile_id: str): return {"id": profile_id}
    def check_dm_available(self, profile) -> bool: return bool(profile.get("dm_open", True))
    def generate_dm(self, profile, context: str): return generate_dm_text(context)
    def send_dm(self, profile, dm: str): return False, "Browser mode is not configured"
    def detect_blocking_state(self): return None
    def stop_agent(self, reason: str): return reason

class AutonomousThreadsAgent:
    def __init__(self, settings, browser: ThreadsBrowserAgent | None = None):
        self.settings = settings
        mode = getattr(settings, "threads_browser_execution_mode", "disabled")
        use_railway_browser = mode == "railway_browser" or (mode == "disabled" and getattr(settings, "autonomous_threads_browser_mode", False))
        self.browser = browser or (ThreadsBrowserLayer(settings) if use_railway_browser else ThreadsBrowserAgent())
        self.worker_queue = ThreadsWorkerQueue(settings.database_path)
        self.runtime_enabled = bool(settings.autonomous_threads_agent_enabled)
        self.dry_run = bool(settings.autonomous_threads_agent_dry_run)
        self.stopped_reason = ""
        self.last_action = "none"
        self.last_error = ""
        self._ensure_db()

    def _connect(self): return sqlite3.connect(self.settings.database_path)

    def _ensure_db(self):
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS autonomous_threads_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, kind TEXT NOT NULL,
                target_id TEXT, profile_id TEXT, score INTEGER DEFAULT 0, status TEXT NOT NULL, reason TEXT, content TEXT)""")
            con.execute("""CREATE TABLE IF NOT EXISTS autonomous_threads_browser_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, thread_url TEXT, profile_url TEXT, keyword TEXT, score INTEGER,
                comment_text TEXT, action_status TEXT, sent_at TEXT, skipped_reason TEXT, browser_error TEXT, semantic_key TEXT)""")

    def record(self, kind, target_id="", profile_id="", score=0, status="ok", reason="", content=""):
        with self._connect() as con:
            con.execute("INSERT INTO autonomous_threads_history(created_at,kind,target_id,profile_id,score,status,reason,content) VALUES(?,?,?,?,?,?,?,?)",
                        (datetime.utcnow().isoformat(), kind, target_id, profile_id, score, status, reason, content))
        self.last_action = f"{kind}:{status}"

    def count_today(self, kind: str, status: str | None = None) -> int:
        prefix = datetime.utcnow().date().isoformat()
        q = "SELECT COUNT(*) FROM autonomous_threads_history WHERE kind=? AND created_at LIKE ?"
        args = [kind, prefix + "%"]
        if status:
            q += " AND status=?"; args.append(status)
        with self._connect() as con: return int(con.execute(q, args).fetchone()[0])

    def profile_contacted_recently(self, profile_id: str, days: int = 14) -> bool:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._connect() as con:
            return con.execute("SELECT 1 FROM autonomous_threads_history WHERE profile_id=? AND kind='dm' AND created_at>=? LIMIT 1", (profile_id, cutoff)).fetchone() is not None

    def is_working_time(self) -> bool:
        now = datetime.now(ZoneInfo(self.settings.autonomous_threads_agent_timezone))
        return self.settings.autonomous_threads_start_hour <= now.hour < self.settings.autonomous_threads_end_hour

    def stop_agent(self, reason: str):
        self.runtime_enabled = False; self.stopped_reason = reason; self.record("stop", status="blocked", reason=reason)

    def startup_summary(self) -> str:
        return ("Autonomous Threads Growth Agent started after deploy\n"
                f"mode: {'dry_run' if self.dry_run else 'live'}\ncomments: {self.settings.autonomous_threads_comments_enabled}\n"
                f"DMs: {self.settings.autonomous_threads_dms_enabled}\nlimits: posts {self.settings.autonomous_threads_daily_post_target}, comments {self.settings.autonomous_threads_daily_comment_limit}, DMs {self.settings.autonomous_threads_daily_dm_limit}, scans {self.settings.autonomous_threads_daily_scan_limit}\n"
                f"working hours: {self.settings.autonomous_threads_start_hour}:00-{self.settings.autonomous_threads_end_hour}:00 {self.settings.autonomous_threads_agent_timezone}")

    def run_once(self) -> AgentActionResult:
        if getattr(self.settings, "autonomous_threads_browser_mode", False) and not self.dry_run:
            return asyncio.run(self.run_once_async())
        return self._run_once_sync()

    async def run_once_async(self) -> AgentActionResult:
        if getattr(self.settings, "autonomous_threads_dms_enabled", False):
            self.last_error = "Live DM is not implemented yet. DM remains disabled/manual."
        mode = getattr(self.settings, "threads_browser_execution_mode", "disabled")
        if mode == "local_worker":
            task = self.worker_queue.create_task("scan_threads", keyword=self._first_search_keyword())
            self.record("scan", task.task_id, status="queued", reason="local_worker", content=task.keyword)
            return AgentActionResult(skipped_reason=f"queued_local_worker:{task.task_id}")
        if (mode == "railway_browser" or getattr(self.settings, "autonomous_threads_browser_mode", False)) and not self.dry_run:
            return await self._run_browser_live_once()
        return self._run_once_sync()

    def _run_once_sync(self) -> AgentActionResult:
        if getattr(self.settings, "autonomous_threads_dms_enabled", False):
            self.last_error = "Live DM is not implemented yet. DM remains disabled/manual."
        if getattr(self.settings, "threads_browser_execution_mode", "disabled") == "local_worker":
            task = self.worker_queue.create_task("scan_threads", keyword=self._first_search_keyword())
            self.record("scan", task.task_id, status="queued", reason="local_worker", content=task.keyword)
            return AgentActionResult(skipped_reason=f"queued_local_worker:{task.task_id}")
        if getattr(self.settings, "autonomous_threads_browser_mode", False) and not self.dry_run:
            return self._run_browser_live_once()
        blocking = self.browser.detect_blocking_state()
        if blocking in BLOCKING_STATES:
            self.stop_agent(blocking); return AgentActionResult(skipped_reason=blocking)
        result = AgentActionResult()
        for thread in self.browser.find_threads(min(self.settings.autonomous_threads_daily_scan_limit, 10)):
            text = self.browser.read_thread_context(thread)
            self.record("scan", thread.get("id", ""), thread.get("profile_id", ""), status="ok", content=text[:500])
            if is_trash_thread(text):
                self.record("skip", thread.get("id", ""), reason="trash", status="skipped"); continue
            score = score_thread_text(text); result.score = score
            if score < 60:
                self.record("skip", thread.get("id", ""), score=score, reason="low_score", status="skipped"); continue
            comment = generate_comment_text(text)
            ok, reason = self.can_comment(thread.get("id", ""), score, comment)
            if ok:
                result.comment_prepared = True; self.record("comment", thread.get("id", ""), score=score, status="prepared", reason=reason, content=comment)
            else: self.record("comment", thread.get("id", ""), score=score, status="skipped", reason=reason, content=comment)
            dm = generate_dm_text(text); result.dm_prepared = score >= self.settings.autonomous_threads_min_dm_score and is_safe_dm(dm)
            self.record("dm", thread.get("id", ""), thread.get("profile_id", ""), score, "prepared" if result.dm_prepared else "skipped", "DMs disabled/manual", dm)
            return result
        result.skipped_reason = "no_relevant_threads"; return result

    async def _run_browser_live_once(self) -> AgentActionResult:
        result = AgentActionResult()
        status = await self.browser.check_browser_ready() if hasattr(self.browser, "check_browser_ready") else None
        if status and not status.session_configured:
            result.skipped_reason = "session not configured"; self.record("comment", status="skipped", reason=result.skipped_reason); return result
        if status and not status.browser_ready:
            result.skipped_reason = status.last_browser_error or "browser_unavailable"; self.record("comment", status="skipped", reason=result.skipped_reason); return result
        ok, reason = await self.browser.open_threads_home()
        if not ok:
            if reason in BLOCKING_STATES:
                self.stop_agent(reason)
            result.skipped_reason = reason; self.record("comment", status="skipped", reason=reason); return result
        keywords = [k.strip() for k in self.settings.autonomous_threads_search_keywords.split(",") if k.strip()]
        city = self.settings.autonomous_threads_city
        for kw in keywords[:5]:
            candidates = (await self.browser.search_threads(f"{kw} {city}".strip()))[:10]
            for cand in candidates:
                self.record("scan", cand.thread_url, cand.profile_url, status="ok", content=cand.text[:500])
                ok, reason = await self.browser.open_thread(cand.thread_url)
                if not ok:
                    if reason in BLOCKING_STATES: self.stop_agent(reason)
                    continue
                text = await self.browser.read_thread_context() or cand.text
                score = score_thread_text(text); result.score = score
                comment = generate_comment_text(text)
                dup_ok, dup_reason = duplicate_guard(self.settings.database_path, cand.thread_url, cand.profile_url, comment, cand.semantic_key or semantic_key(text))
                can, can_reason = self.can_comment(cand.thread_url, score, comment, profile_url=cand.profile_url, semantic_key_value=cand.semantic_key or semantic_key(text), duplicate_ok=dup_ok, duplicate_reason=dup_reason)
                if not can:
                    self.browser.save_action_history(self.settings.database_path, thread_url=cand.thread_url, profile_url=cand.profile_url, keyword=kw, score=score, comment_text=comment, action_status="skipped", sent_at=datetime.utcnow().isoformat(), skipped_reason=can_reason, browser_error=self.browser.last_browser_error, semantic_key=cand.semantic_key)
                    self.record("comment", cand.thread_url, cand.profile_url, score, "skipped", can_reason, comment); continue
                sent, pub_reason = await self.browser.publish_comment(cand, comment)
                self.browser.save_action_history(self.settings.database_path, thread_url=cand.thread_url, profile_url=cand.profile_url, keyword=kw, score=score, comment_text=comment, action_status="sent" if sent else "skipped", sent_at=datetime.utcnow().isoformat(), skipped_reason="" if sent else pub_reason, browser_error=self.browser.last_browser_error, semantic_key=cand.semantic_key)
                self.record("comment", cand.thread_url, cand.profile_url, score, "sent" if sent else "skipped", pub_reason, comment)
                result.published_comment = bool(sent); result.skipped_reason = "" if sent else pub_reason
                return result
        result.skipped_reason = "no_relevant_threads"; return result

    def _first_search_keyword(self) -> str:
        keywords = [k.strip() for k in self.settings.autonomous_threads_search_keywords.split(",") if k.strip()]
        base = keywords[0] if keywords else "заявки"
        return f"{base} {self.settings.autonomous_threads_city}".strip()

    def can_comment(self, thread_id: str, score: int, comment: str, profile_url: str = "", semantic_key_value: str = "", duplicate_ok: bool = True, duplicate_reason: str = "ok"):
        if self.dry_run: return score >= self.settings.autonomous_threads_min_comment_score and is_safe_comment(comment), "dry_run_prepare"
        if not self.settings.autonomous_threads_comments_enabled: return False, "comments_disabled"
        if score < self.settings.autonomous_threads_min_comment_score: return False, "low_score"
        if self.count_today("comment", "sent") >= self.settings.autonomous_threads_daily_comment_limit: return False, "daily_comment_limit"
        if getattr(self.settings, "threads_browser_execution_mode", "disabled") == "local_worker": return True, "local_worker_allowed"
        if not getattr(self.settings, "autonomous_threads_browser_mode", False): return False, "browser_mode_disabled"
        if hasattr(self.browser, "session_configured") and not self.browser.session_configured(): return False, "session not configured"
        if not self.is_working_time(): return False, "outside_working_hours"
        if self.has_target_action("comment", thread_id): return False, "duplicate_thread"
        if not duplicate_ok: return False, duplicate_reason
        if not is_safe_comment(comment): return False, "comment_safety"
        return True, "ok"

    def can_dm(self, profile_id: str, score: int, dm_open: bool, dm: str):
        if not dm_open: return False, "dm_closed"
        if self.dry_run: return score >= self.settings.autonomous_threads_min_dm_score and is_safe_dm(dm), "dry_run_prepare"
        if score < self.settings.autonomous_threads_min_dm_score: return False, "low_score"
        if self.count_today("dm", "sent") >= self.settings.autonomous_threads_daily_dm_limit: return False, "daily_dm_limit"
        if self.profile_contacted_recently(profile_id): return False, "duplicate_profile_14d"
        return False, "Live DM is not implemented yet. DM remains disabled/manual."
        if not is_safe_dm(dm): return False, "dm_safety"
        return True, "ok"

    def has_target_action(self, kind, target_id):
        with self._connect() as con: return con.execute("SELECT 1 FROM autonomous_threads_history WHERE kind=? AND target_id=? LIMIT 1", (kind, target_id)).fetchone() is not None

    def history(self, limit=10):
        with self._connect() as con:
            return con.execute("SELECT created_at,kind,target_id,profile_id,score,status,reason FROM autonomous_threads_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    def report(self) -> str:
        scans = self.count_today("scan"); trash = self.count_today("skip", "skipped"); comments_sent = self.count_today("comment", "sent"); comments_prepared = self.count_today("comment", "prepared"); dms_sent = self.count_today("dm", "sent"); dms_prepared = self.count_today("dm", "prepared"); stops = self.count_today("stop", "blocked")
        bs = None

        session = "yes" if bs and bs.session_configured else "no"
        browser_ready = "yes" if bs and bs.browser_ready else "no"
        unavailable = "Live DM is not implemented yet. DM remains disabled/manual."
        browser_error = getattr(self.browser, 'last_browser_error', '') or ('Browser mode is not configured' if self.settings.autonomous_threads_browser_mode and not bs else 'нет')
        return ("📊 Autonomous Threads Growth Agent — daily report\n\n📝 Контент:\n• posts published: 0\n• queue: managed by Threads autoposting\n\n"
                f"🔍 Поиск:\n• threads scanned: {scans}\n• trash skipped: {trash}\n• relevant threads: {max(0, scans-trash)}\n\n"
                f"💬 Комментарии:\n• comments sent: {comments_sent}\n• comments prepared: {comments_prepared}\n• skipped by safety: {self.count_today('comment','skipped')}\n• skipped duplicates: tracked\n\n"
                f"📩 DM:\n• DMs sent: {dms_sent}\n• DM closed: tracked\n• skipped: {self.count_today('dm','skipped')}\n• {unavailable}\n\n"
                "🔥 Лиды:\n• leads found: tracked from relevant threads\n• score 80+: tracked\n• hot leads: owner notification on inbound/handoff\n\n"
                f"🌐 Browser Layer:\n• browser mode: {self.settings.autonomous_threads_browser_mode}\n• browser ready: {browser_ready}\n• session: {session}\n• comments live enabled: {self.settings.autonomous_threads_comments_enabled}\n• DMs live enabled: no\n• threads scanned: {scans}\n• candidates found: {max(0, scans-trash)}\n• comments sent: {comments_sent}\n• comments prepared: {comments_prepared}\n• skipped safety: {self.count_today('comment','skipped')}\n• skipped duplicate: tracked\n• skipped no session: tracked\n• skipped browser unavailable: tracked\n• browser errors: {browser_error}\n• stopped reason: {self.stopped_reason or getattr(self.browser, 'stopped_reason', '') or 'none'}\n\n"
                f"⚠️ Ошибки:\n• captcha/checkpoint/rate limit/action blocked: {stops}\n• browser issue: {getattr(self.browser, 'last_browser_error', '') or 'нет'}\n• API issue: {self.last_error or 'нет'}\n\n🧠 Рекомендация на завтра:\nУсилить поиск по нишам Алматы и не превышать лимиты.")


    async def report_async(self) -> str:
        scans = self.count_today("scan"); trash = self.count_today("skip", "skipped"); comments_sent = self.count_today("comment", "sent"); comments_prepared = self.count_today("comment", "prepared"); dms_sent = self.count_today("dm", "sent"); dms_prepared = self.count_today("dm", "prepared"); stops = self.count_today("stop", "blocked")
        bs = await self.browser.check_browser_ready() if hasattr(self.browser, "check_browser_ready") else None
        session = "yes" if bs and bs.session_configured else "no"
        browser_ready = "yes" if bs and bs.browser_ready else "no"
        unavailable = "Live DM is not implemented yet. DM remains disabled/manual."
        browser_error = getattr(self.browser, 'last_browser_error', '') or ('Browser mode is not configured' if self.settings.autonomous_threads_browser_mode and bs and not bs.session_configured else 'нет')
        return ("📊 Autonomous Threads Growth Agent — daily report\n\n📝 Контент:\n• posts published: 0\n• queue: managed by Threads autoposting\n\n"
                f"🔍 Поиск:\n• threads scanned: {scans}\n• trash skipped: {trash}\n• relevant threads: {max(0, scans-trash)}\n\n"
                f"💬 Комментарии:\n• comments sent: {comments_sent}\n• comments prepared: {comments_prepared}\n• skipped by safety: {self.count_today('comment','skipped')}\n• skipped duplicates: tracked\n\n"
                f"📩 DM:\n• DMs sent: {dms_sent}\n• DM closed: tracked\n• skipped: {self.count_today('dm','skipped')}\n• {unavailable}\n\n"
                "🔥 Лиды:\n• leads found: tracked from relevant threads\n• score 80+: tracked\n• hot leads: owner notification on inbound/handoff\n\n"
                f"🌐 Browser Layer:\n• browser mode: {self.settings.autonomous_threads_browser_mode}\n• browser ready: {browser_ready}\n• session: {session}\n• comments live enabled: {self.settings.autonomous_threads_comments_enabled}\n• DMs live enabled: no\n• threads scanned: {scans}\n• candidates found: {max(0, scans-trash)}\n• comments sent: {comments_sent}\n• comments prepared: {comments_prepared}\n• skipped safety: {self.count_today('comment','skipped')}\n• skipped duplicate: tracked\n• skipped no session: tracked\n• skipped browser unavailable: tracked\n• browser errors: {browser_error}\n• stopped reason: {self.stopped_reason or getattr(self.browser, 'stopped_reason', '') or 'none'}\n\n"
                f"⚠️ Ошибки:\n• captcha/checkpoint/rate limit/action blocked: {stops}\n• browser issue: {getattr(self.browser, 'last_browser_error', '') or 'нет'}\n• API issue: {self.last_error or 'нет'}\n\n🧠 Рекомендация на завтра:\nУсилить поиск по нишам Алматы и не превышать лимиты.")


def is_trash_thread(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in TRASH_WORDS) or not any(w in low for w in BUSINESS_WORDS)

def score_thread_text(text: str) -> int:
    low = (text or "").lower(); score = 20
    for word in BUSINESS_WORDS:
        if word in low: score += 8
    for niche in ["салон", "маникюр", "косметолог", "стомат", "клиник", "барбершоп", "массаж", "школ", "эксперт"]:
        if niche in low: score += 8
    if "алматы" in low or "казахстан" in low: score += 5
    if is_trash_thread(text): score -= 40
    return max(0, min(100, score))

def generate_comment_text(text: str) -> str:
    return "Часто проблема не в количестве заявок, а в скорости первого ответа и follow-up: без фиксации в CRM тёплый клиент быстро теряется."

def generate_dm_text(text: str) -> str:
    return "Здравствуйте! Увидел, что у вас много записей через Direct/WhatsApp. Часто там теряются тёплые заявки; могу показать короткую схему, как AI-администратор фиксирует запрос и follow-up."

def is_safe_comment(text: str) -> bool:
    low = (text or "").lower()
    return len(text) <= 300 and not re.search(r"https?://|www\.|wa\.me|t\.me", low) and "₸" not in text and "тенге" not in low and "напишите" not in low and "пиши" not in low

def is_safe_dm(text: str) -> bool:
    low = (text or "").lower()
    pressure = any(p in low for p in ["срочно", "только сегодня", "последний шанс", "обязаны"])
    return len(text) <= 500 and not re.search(r"https?://|www\.|wa\.me|t\.me", low) and "₸" not in text and "тенге" not in low and not pressure
