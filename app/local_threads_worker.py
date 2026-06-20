from __future__ import annotations

import asyncio
import os
from app.autonomous_threads_agent import generate_comment_text, score_thread_text
from app.autonomous_threads_agent import is_safe_comment
from app.threads_browser_layer import BLOCKING_PATTERNS, THREADS_HOME
from app.threads_worker_client import ThreadsWorkerQueue, WorkerTask

BLOCKING_FINAL = {"captcha", "checkpoint", "rate_limit", "action_blocked", "suspicious_activity"}


class LocalThreadsBrowserWorker:
    def __init__(self, database_path: str, user_data_dir: str = "./threads_chrome_profile", headless: bool = False):
        self.queue = ThreadsWorkerQueue(database_path)
        self.user_data_dir = user_data_dir
        self.headless = headless
        self.last_error = ""
        self._playwright = None
        self._context = None
        self._page = None

    async def start_browser(self):
        if self._page is not None:
            return
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        os.makedirs(self.user_data_dir, exist_ok=True)
        self._context = await self._playwright.chromium.launch_persistent_context(
            self.user_data_dir,
            headless=self.headless,
            args=["--disable-dev-shm-usage"],
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(10000)

    async def close(self):
        for obj in [self._context]:
            try:
                if obj:
                    await obj.close()
            except Exception:
                pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._playwright = self._context = self._page = None

    async def detect_blocking_state(self) -> str | None:
        if self._page is None:
            return None
        text = ((await self._page.content()) + " " + (await self._page.title())).lower()
        for state, patterns in BLOCKING_PATTERNS.items():
            if any(p in text for p in patterns):
                return state
        return None

    async def browser_test(self) -> dict:
        await self.start_browser()
        await self._page.goto(THREADS_HOME, wait_until="domcontentloaded", timeout=30000)
        blocking = await self.detect_blocking_state()
        return {"opened": blocking is None, "login_state": "ok" if blocking is None else blocking, "captcha_checkpoint": blocking in {"captcha", "checkpoint"}}

    async def scan_once(self, keyword: str) -> dict:
        await self.start_browser()
        await self._page.goto(f"https://www.threads.net/search?q={keyword}", wait_until="domcontentloaded", timeout=30000)
        blocking = await self.detect_blocking_state()
        if blocking:
            return {"blocked": blocking}
        body = (await self._page.locator("body").inner_text(timeout=5000))[:4000]
        score = score_thread_text(body)
        comment = generate_comment_text(body)
        links = await self._page.locator("a[href]").evaluate_all("els => els.map(a => a.href).filter(h => h.includes('threads.net') && h.includes('/@'))")
        thread_url = links[0] if links else ""
        return {"opened": True, "thread_url": thread_url, "score": score, "comment_text": comment, "context_preview": body[:500], "dm": "manual_only"}

    async def comment_thread(self, task: WorkerTask, dry_run: bool, comments_enabled: bool, daily_comment_limit: int) -> dict:
        if dry_run or not comments_enabled:
            return {"published": False, "reason": "dry_run" if dry_run else "comments_disabled", "dm": "manual_only"}
        if daily_comment_limit <= 0:
            return {"published": False, "reason": "daily_comment_limit", "dm": "manual_only"}
        await self.start_browser()
        await self._page.goto(task.thread_url, wait_until="domcontentloaded", timeout=30000)
        blocking = await self.detect_blocking_state()
        if blocking:
            return {"blocked": blocking}
        if not is_safe_comment(task.comment_text):
            return {"published": False, "reason": "comment_safety", "dm": "manual_only"}
        box = None
        for selector in ["textarea", "[contenteditable=\'true\']"]:
            loc = self._page.locator(selector).last
            if await loc.count():
                box = loc
                break
        if box is None:
            return {"published": False, "reason": "comment_input_selector_missing", "dm": "manual_only"}
        await box.fill(task.comment_text, timeout=5000)
        buttons = self._page.get_by_role("button")
        publish = None
        for i in range(min(await buttons.count(), 20)):
            b = buttons.nth(i)
            label = (await b.inner_text(timeout=1000) or "").lower()
            if any(x in label for x in ["post", "reply", "отправ", "ответ"]):
                publish = b
                break
        if publish is None:
            return {"published": False, "reason": "publish_button_selector_missing", "dm": "manual_only"}
        await publish.click(timeout=5000)
        return {"published": True, "reason": "sent", "comment_text": task.comment_text, "dm": "manual_only"}

    async def execute(self, task: WorkerTask, dry_run: bool = True, comments_enabled: bool = False, daily_comment_limit: int = 5) -> tuple[str, dict, str, int | None]:
        try:
            if task.task_type == "browser_test":
                result = await self.browser_test()
                if result.get("login_state") in BLOCKING_FINAL:
                    return "blocked", result, result["login_state"], None
                return "done", result, "", None
            if task.task_type == "scan_threads":
                result = await self.scan_once(task.keyword)
                if result.get("blocked"):
                    return "blocked", result, result["blocked"], None
                return "done", result, "", result.get("score")
            if task.task_type == "comment_thread":
                result = await self.comment_thread(task, dry_run, comments_enabled, daily_comment_limit)
                if result.get("blocked"):
                    return "blocked", result, result["blocked"], None
                return "done", result, "", None
            return "failed", {}, "unsupported_task_type", None
        except Exception as exc:
            self.last_error = str(exc)[:300]
            return "failed", {}, self.last_error, None

    async def run_forever(self, poll_interval_seconds: int = 30, dry_run: bool = True, comments_enabled: bool = False, daily_comment_limit: int = 5):
        while True:
            self.queue.heartbeat(self.last_error)
            task = self.queue.claim_next()
            if task:
                status, result, error, score = await self.execute(task, dry_run, comments_enabled, min(5, daily_comment_limit))
                self.queue.update_task(task.task_id, status, result, error, score)
                if status == "blocked":
                    print(f"Worker stopped: {error}. Please solve it manually in Chrome; no bypass attempted.")
                    break
            await asyncio.sleep(poll_interval_seconds)
