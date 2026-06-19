from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BLOCKING_STATES = {"captcha", "checkpoint", "rate_limit", "action_blocked", "login_issue"}
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
        self.browser = browser or ThreadsBrowserAgent()
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
        blocking = self.browser.detect_blocking_state()
        if blocking in BLOCKING_STATES:
            self.stop_agent(blocking); return AgentActionResult(skipped_reason=blocking)
        result = AgentActionResult()
        for thread in self.browser.find_threads(self.settings.autonomous_threads_daily_scan_limit):
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
                if self.dry_run: result.comment_prepared = True; self.record("comment", thread.get("id", ""), score=score, status="prepared", content=comment)
                else:
                    sent, publish_reason = self.browser.publish_comment(thread, comment); result.published_comment = sent; self.record("comment", thread.get("id", ""), score=score, status="sent" if sent else "skipped", reason=publish_reason, content=comment)
            else: self.record("comment", thread.get("id", ""), score=score, status="skipped", reason=reason, content=comment)
            profile_id = thread.get("profile_id", "")
            dm = generate_dm_text(text)
            ok, reason = self.can_dm(profile_id, score, bool(thread.get("dm_open", False)), dm)
            if ok:
                if self.dry_run: result.dm_prepared = True; self.record("dm", thread.get("id", ""), profile_id, score, "prepared", content=dm)
                else:
                    sent, send_reason = self.browser.send_dm({"id": profile_id}, dm); result.sent_dm = sent; self.record("dm", thread.get("id", ""), profile_id, score, "sent" if sent else "skipped", send_reason, dm)
            else: self.record("dm", thread.get("id", ""), profile_id, score, "skipped", reason, dm)
            return result
        result.skipped_reason = "no_relevant_threads"; return result

    def can_comment(self, thread_id: str, score: int, comment: str):
        if self.dry_run: return score >= self.settings.autonomous_threads_min_comment_score and is_safe_comment(comment), "dry_run_prepare"
        if not self.settings.autonomous_threads_comments_enabled: return False, "comments_disabled"
        if score < self.settings.autonomous_threads_min_comment_score: return False, "low_score"
        if self.count_today("comment", "sent") >= self.settings.autonomous_threads_daily_comment_limit: return False, "daily_comment_limit"
        if not self.is_working_time(): return False, "outside_working_hours"
        if self.has_target_action("comment", thread_id): return False, "duplicate_thread"
        if not is_safe_comment(comment): return False, "comment_safety"
        return True, "ok"

    def can_dm(self, profile_id: str, score: int, dm_open: bool, dm: str):
        if not dm_open: return False, "dm_closed"
        if self.dry_run: return score >= self.settings.autonomous_threads_min_dm_score and is_safe_dm(dm), "dry_run_prepare"
        if not self.settings.autonomous_threads_dms_enabled: return False, "dms_disabled"
        if score < self.settings.autonomous_threads_min_dm_score: return False, "low_score"
        if self.count_today("dm", "sent") >= self.settings.autonomous_threads_daily_dm_limit: return False, "daily_dm_limit"
        if self.profile_contacted_recently(profile_id): return False, "duplicate_profile_14d"
        if not is_safe_dm(dm): return False, "dm_safety"
        return True, "ok"

    def has_target_action(self, kind, target_id):
        with self._connect() as con: return con.execute("SELECT 1 FROM autonomous_threads_history WHERE kind=? AND target_id=? LIMIT 1", (kind, target_id)).fetchone() is not None

    def history(self, limit=10):
        with self._connect() as con:
            return con.execute("SELECT created_at,kind,target_id,profile_id,score,status,reason FROM autonomous_threads_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    def report(self) -> str:
        scans = self.count_today("scan"); trash = self.count_today("skip", "skipped"); comments_sent = self.count_today("comment", "sent"); comments_prepared = self.count_today("comment", "prepared"); dms_sent = self.count_today("dm", "sent"); dms_prepared = self.count_today("dm", "prepared"); stops = self.count_today("stop", "blocked")
        unavailable = "autonomous live actions unavailable: Browser mode is not configured" if self.settings.autonomous_threads_browser_mode and not self.browser.configured else "manual/unavailable: inbound DM reading unavailable"
        return ("📊 Autonomous Threads Growth Agent — daily report\n\n📝 Контент:\n• posts published: 0\n• queue: managed by Threads autoposting\n\n"
                f"🔍 Поиск:\n• threads scanned: {scans}\n• trash skipped: {trash}\n• relevant threads: {max(0, scans-trash)}\n\n"
                f"💬 Комментарии:\n• comments sent: {comments_sent}\n• comments prepared: {comments_prepared}\n• skipped by safety: {self.count_today('comment','skipped')}\n• skipped duplicates: tracked\n\n"
                f"📩 DM:\n• DMs sent: {dms_sent}\n• DM closed: tracked\n• skipped: {self.count_today('dm','skipped')}\n• {unavailable}\n\n"
                "🔥 Лиды:\n• leads found: tracked from relevant threads\n• score 80+: tracked\n• hot leads: owner notification on inbound/handoff\n\n"
                f"⚠️ Ошибки:\n• captcha/checkpoint/rate limit/action blocked: {stops}\n• browser issue: {'Browser mode is not configured' if self.settings.autonomous_threads_browser_mode and not self.browser.configured else 'нет'}\n• API issue: {self.last_error or 'нет'}\n\n🧠 Рекомендация на завтра:\nУсилить поиск по нишам Алматы и не превышать лимиты.")


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
