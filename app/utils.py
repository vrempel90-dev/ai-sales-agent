"""Small utility helpers."""
def truncate(text: str, limit: int = 500) -> str:
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."
