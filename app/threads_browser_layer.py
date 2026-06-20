from __future__ import annotations

import json
import os
import re
import sqlite3
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

THREADS_HOME = "https://www.threads.net/"
BLOCKING_PATTERNS = {
    "captcha": ["captcha", "verify you are human", "подтвердите, что вы человек"],
    "checkpoint": ["checkpoint", "security check", "проверка безопасности"],
    "login_issue": ["log in", "login", "sign in", "войдите", "session expired"],
    "suspicious_activity": ["suspicious activity", "подозрительная активность"],
    "action_blocked": ["action blocked", "действие заблокировано", "try again later"],
    "rate_limit": ["rate limit", "too many requests", "слишком много запросов"],
}

@dataclass
class BrowserStatus:
    playwright_installed: bool = False
    browser_mode_enabled: bool = False
    session_configured: bool = False
    browser_ready: bool = False
    live_comments_ready: bool = False
    live_dm_ready: bool = False
    can_open_threads_home: bool = False
    login_state: str = "unknown"
    last_browser_error: str = ""
    stopped_reason: str = ""

@dataclass
class ThreadCandidate:
    thread_url: str
    profile_url: str = ""
    text: str = ""
    keyword: str = ""
    semantic_key: str = ""
    author_key: str = ""

class ThreadsBrowserLayer:
    configured = False

    def __init__(self, settings):
        self.settings = settings
        self.enabled = bool(getattr(settings, "autonomous_threads_browser_mode", False))
        self.headless = bool(getattr(settings, "autonomous_threads_browser_headless", True))
        self.cookies_json = getattr(settings, "autonomous_threads_cookies_json", "") or ""
        self.session_file = getattr(settings, "autonomous_threads_session_file", "") or ""
        self.user_data_dir = getattr(settings, "autonomous_threads_user_data_dir", "") or ""
        self.last_browser_error = ""
        self.stopped_reason = ""
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self.configured = self.session_configured()


    def _browser_launch_args(self) -> list[str]:
        return [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-setuid-sandbox",
        ]

    def _short_browser_error(self, exc: Exception) -> str:
        raw = str(exc).strip() or exc.__class__.__name__
        lowered = raw.lower()
        if "executable doesn't exist" in lowered or "executable does not exist" in lowered or "browser executable" in lowered:
            prefix = "executable not found"
        elif "please run" in lowered and "playwright install" in lowered:
            prefix = "missing browser binaries"
        elif "host system is missing dependencies" in lowered or "missing dependencies" in lowered or "install-deps" in lowered:
            prefix = "missing system dependencies"
        elif "timeout" in lowered or isinstance(exc, TimeoutError):
            prefix = "launch timeout"
        elif "sandbox" in lowered or "no usable sandbox" in lowered:
            prefix = "sandbox issue"
        elif "permission denied" in lowered or "eacces" in lowered or "operation not permitted" in lowered:
            prefix = "permission issue"
        else:
            prefix = "browser launch failed"
        compact = " ".join(raw.split())
        return f"{prefix}: {compact[:220]}"

    def playwright_installed(self) -> bool:
        try:
            import playwright.sync_api  # noqa: F401
            return True
        except Exception:
            return False

    def session_configured(self) -> bool:
        profile_ready = bool(self.user_data_dir.strip() and os.path.isdir(self.user_data_dir) and any(os.scandir(self.user_data_dir)))
        return bool(self.cookies_json.strip() or self.session_file.strip() or profile_ready)

    def check_browser_ready(self) -> BrowserStatus:
        installed = self.playwright_installed()
        session = self.session_configured()
        ready = bool(self.enabled and installed and session)
        if ready and self._page is None:
            launched, reason = self.load_session()
            ready = launched
            if not launched and not self.last_browser_error:
                self.last_browser_error = reason
        if self.enabled and not self.headless:
            host = socket.gethostname().lower()
            if "railway" in os.environ or "RAILWAY_ENVIRONMENT" in os.environ or "railway" in host:
                self.last_browser_error = self.last_browser_error or "headless=false is not recommended on Railway; set AUTONOMOUS_THREADS_BROWSER_HEADLESS=true"
        return BrowserStatus(
            playwright_installed=installed,
            browser_mode_enabled=self.enabled,
            session_configured=session,
            browser_ready=ready,
            live_comments_ready=bool(ready and not getattr(self.settings, "autonomous_threads_agent_dry_run", True) and getattr(self.settings, "autonomous_threads_comments_enabled", False)),
            live_dm_ready=False,
            last_browser_error=self.last_browser_error,
            stopped_reason=self.stopped_reason,
        )

    def load_session(self) -> tuple[bool, str]:
        if not self.enabled:
            return False, "browser_mode_disabled"
        if not self.playwright_installed():
            return False, "browser_dependencies_missing"
        if not self.session_configured():
            return False, "session not configured"
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            if self.user_data_dir:
                self._context = self._playwright.chromium.launch_persistent_context(
                    self.user_data_dir, headless=self.headless, args=self._browser_launch_args()
                )
            else:
                self._browser = self._playwright.chromium.launch(headless=self.headless, args=self._browser_launch_args())
                kwargs: dict[str, Any] = {}
                if self.session_file and os.path.exists(self.session_file):
                    kwargs["storage_state"] = self.session_file
                self._context = self._browser.new_context(**kwargs)
                if self.cookies_json.strip():
                    self._context.add_cookies(json.loads(self.cookies_json))
            self._page = self._context.new_page()
            return True, "ok"
        except Exception as exc:
            self.last_browser_error = self._short_browser_error(exc)
            self.close_browser()
            return False, "browser_unavailable"

    def open_threads_home(self) -> tuple[bool, str]:
        if self._page is None:
            ok, reason = self.load_session()
            if not ok:
                return False, reason
        try:
            self._page.goto(THREADS_HOME, wait_until="domcontentloaded", timeout=30000)
            blocking = self.detect_blocking_state()
            if blocking:
                return False, blocking
            return True, "ok"
        except Exception as exc:
            self.last_browser_error = str(exc)
            return False, "browser_error"

    def detect_blocking_state(self):
        if self._page is None:
            return None
        try:
            text = ((self._page.content() or "") + " " + (self._page.title() or "")).lower()
        except Exception as exc:
            self.last_browser_error = str(exc)
            return "interface_changed"
        for state, patterns in BLOCKING_PATTERNS.items():
            if any(p in text for p in patterns):
                self.stopped_reason = state
                return state
        return None

    def search_threads(self, keyword: str):
        if self._page is None:
            ok, reason = self.open_threads_home()
            if not ok:
                self.stopped_reason = reason
                return []
        try:
            self._page.goto(f"https://www.threads.net/search?q={quote_plus(keyword)}", wait_until="domcontentloaded", timeout=30000)
            if self.detect_blocking_state():
                return []
            return self.collect_candidate_threads(10, keyword)
        except Exception as exc:
            self.last_browser_error = str(exc)
            return []

    def collect_candidate_threads(self, limit: int = 10, keyword: str = ""):
        if self._page is None:
            return []
        try:
            links = self._page.locator("a[href]").evaluate_all("els => els.map(a => ({href: a.href, text: a.innerText || ''}))")
        except Exception as exc:
            self.last_browser_error = str(exc)
            self.stopped_reason = "interface_changed"
            return []
        out = []
        seen = set()
        for item in links:
            href = item.get("href", "")
            if "threads.net" not in href or href in seen:
                continue
            if "/@" not in href:
                continue
            seen.add(href)
            profile = href.split("/post/")[0] if "/post/" in href else href
            out.append(ThreadCandidate(href, profile, item.get("text", ""), keyword, semantic_key(href + keyword), profile))
            if len(out) >= min(limit, 10):
                break
        return out

    def open_thread(self, url: str):
        if self._page is None:
            return False, "browser_not_started"
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            blocking = self.detect_blocking_state()
            return (False, blocking) if blocking else (True, "ok")
        except Exception as exc:
            self.last_browser_error = str(exc)
            return False, "browser_error"

    def read_thread_context(self):
        if self._page is None:
            return ""
        try:
            return self._page.locator("body").inner_text(timeout=5000)[:4000]
        except Exception as exc:
            self.last_browser_error = str(exc)
            self.stopped_reason = "interface_changed"
            return ""

    def score_thread_candidate(self, text: str) -> int:
        from app.autonomous_threads_agent import score_thread_text
        return score_thread_text(text)

    def generate_comment(self, text: str) -> str:
        from app.autonomous_threads_agent import generate_comment_text
        return generate_comment_text(text)

    def publish_comment(self, thread: dict | ThreadCandidate, comment: str):
        if self._page is None:
            return False, "browser_not_started"
        blocking = self.detect_blocking_state()
        if blocking:
            return False, blocking
        selectors = ["textarea", "[contenteditable='true']"]
        try:
            box = None
            for selector in selectors:
                loc = self._page.locator(selector).last
                if loc.count():
                    box = loc
                    break
            if box is None:
                return False, "comment_input_selector_missing"
            box.fill(comment)
            buttons = self._page.get_by_role("button")
            publish = None
            for i in range(min(buttons.count(), 20)):
                b = buttons.nth(i)
                label = (b.inner_text(timeout=1000) or "").lower()
                if any(x in label for x in ["post", "reply", "отправ", "ответ"]):
                    publish = b
                    break
            if publish is None:
                return False, "publish_button_selector_missing"
            publish.click(timeout=5000)
            return True, "sent"
        except Exception as exc:
            self.last_browser_error = str(exc)
            return False, "browser_error"

    def save_action_history(self, db_path: str, **fields):
        cols = ["thread_url","profile_url","keyword","score","comment_text","action_status","sent_at","skipped_reason","browser_error","semantic_key"]
        with sqlite3.connect(db_path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS autonomous_threads_browser_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, thread_url TEXT, profile_url TEXT, keyword TEXT, score INTEGER,
                comment_text TEXT, action_status TEXT, sent_at TEXT, skipped_reason TEXT, browser_error TEXT, semantic_key TEXT)""")
            con.execute(f"INSERT INTO autonomous_threads_browser_history({','.join(cols)}) VALUES({','.join('?' for _ in cols)})", [fields.get(c, "") for c in cols])

    def close_browser(self):
        for obj in [self._context, self._browser]:
            try:
                if obj: obj.close()
            except Exception:
                pass
        try:
            if self._playwright: self._playwright.stop()
        except Exception:
            pass
        self._page = self._context = self._browser = self._playwright = None


def semantic_key(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()[:160]


def duplicate_guard(db_path: str, thread_url: str, profile_url: str, comment_text: str, sem_key: str, days: int = 14) -> tuple[bool, str]:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    norm_comment = semantic_key(comment_text)
    with sqlite3.connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS autonomous_threads_browser_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, thread_url TEXT, profile_url TEXT, keyword TEXT, score INTEGER,
            comment_text TEXT, action_status TEXT, sent_at TEXT, skipped_reason TEXT, browser_error TEXT, semantic_key TEXT)""")
        checks = [
            ("duplicate_thread", "thread_url=?", thread_url),
            ("duplicate_profile_14d", "profile_url=? AND sent_at>=?", profile_url),
            ("duplicate_semantic_key", "semantic_key=?", sem_key),
        ]
        for reason, where, value in checks:
            args = (value, cutoff) if "sent_at" in where else (value,)
            if value and con.execute(f"SELECT 1 FROM autonomous_threads_browser_history WHERE {where} LIMIT 1", args).fetchone():
                return False, reason
        rows = con.execute("SELECT comment_text FROM autonomous_threads_browser_history WHERE sent_at>=?", (cutoff,)).fetchall()
        for (old,) in rows:
            if norm_comment and semantic_key(old) == norm_comment:
                return False, "duplicate_comment_text"
    return True, "ok"
