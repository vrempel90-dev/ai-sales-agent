"""Safety filters for public replies."""
SPAM_MARKERS = ("http://", "https://", "заработок", "крипта", "казино", "подпишись", "18+")
TOXIC_MARKERS = ("дурак", "идиот", "тупой", "ненавижу", "лох", "мошенник")
FORBIDDEN_PROMISES = ("гарантирован", "100%", "точно приведем", "любое количество заявок")


def is_spam(text: str) -> bool:
    value = text.lower()
    return any(marker in value for marker in SPAM_MARKERS) or value.count("@") > 3


def is_toxic(text: str) -> bool:
    value = text.lower()
    return any(marker in value for marker in TOXIC_MARKERS)


def should_ignore(text: str) -> bool:
    return not text.strip() or is_spam(text) or is_toxic(text)


def clean_ai_reply(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    for phrase in FORBIDDEN_PROMISES:
        cleaned = cleaned.replace(phrase, "")
    if len(cleaned) > 500:
        cleaned = cleaned[:497].rstrip() + "..."
    return cleaned
