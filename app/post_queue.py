from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class QueuedPost:
    id: int
    text: str
    status: str
    created_at: str

class PostQueue:
    def __init__(self):
        self._posts: dict[int, QueuedPost] = {}
        self._next_id = 1
    def add_post(self, text: str) -> QueuedPost:
        post = QueuedPost(self._next_id, text.strip(), "draft", datetime.now(timezone.utc).isoformat())
        self._posts[post.id] = post; self._next_id += 1; return post
    def get_post(self, id: int): return self._posts.get(id)
    def list_posts(self): return list(self._posts.values())
    def approve_post(self, id: int):
        p=self.get_post(id); 
        if p: p.status="approved"
        return p
    def skip_post(self, id: int):
        p=self.get_post(id); 
        if p: p.status="skipped"
        return p
    def mark_published(self, id: int):
        p=self.get_post(id); 
        if p: p.status="published"
        return p
    def get_next_draft(self):
        return next((p for p in self.list_posts() if p.status == "draft"), None)
    def update_post(self, id: int, text: str):
        p=self.get_post(id)
        if p:
            p.text=text.strip(); p.status="draft"
        return p

post_queue = PostQueue()
