"""Rule-based lead scoring."""
PRICE_WORDS = ("сколько стоит", "цена", "стоимость", "прайс")
TIMING_WORDS = ("срок", "когда", "как быстро", "за сколько")
INTENT_WORDS = ("хочу", "нужно", "можно консультацию", "хочу внедрить", "интересует")
CONTACT_WORDS = ("телефон", "whatsapp", "telegram", "созвон", "разбор", "+7", "@")


def calculate_lead_score(text: str, analysis: dict) -> int:
    value = text.lower()
    score = 0
    if analysis.get("business_type"):
        score += 20
    if analysis.get("pain"):
        score += 20
    if any(word in value for word in PRICE_WORDS):
        score += 15
    if any(word in value for word in TIMING_WORDS):
        score += 15
    if any(word in value for word in INTENT_WORDS):
        score += 20
    if any(word in value for word in CONTACT_WORDS) or analysis.get("should_notify_viktor"):
        score += 10
    return min(score, 100)


def get_lead_status(score: int) -> str:
    if score >= 70:
        return "hot"
    if score >= 40:
        return "warm"
    return "cold"


def should_notify(score: int, threshold: int) -> bool:
    return score >= threshold
