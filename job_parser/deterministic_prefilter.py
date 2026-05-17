import re
from typing import TypedDict


class PrefilterResult(TypedDict):
    accepted: bool
    score: int
    matched_positive: list[str]
    matched_negative: list[str]


POSITIVE = [
    (r"\b(hiring|vacanc(y|ies)|job opening|looking for)\b", 4),
    (r"\b(freelance|contract|full[- ]time|part[- ]time|intern(ship)?)\b", 3),
    (r"\b(send cv|send portfolio|apply|contact|dm)\b", 2),
    (r"ищем|ваканси(я|и)|требуется|нужен", 4),
]

NEGATIVE = [
    (r"\b(news|podcast|interview|article|webinar|conference|event|meetup|opinion|showcase)\b", -5),
    (r"новост|подкаст|интервью|статья|вебинар|конференц|мероприяти|мнение", -5),
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TG_RE = re.compile(r"@[A-Za-z0-9_]{4,}")
SALARY_RE = re.compile(r"(\$|€|₽|руб\.?|usd|eur|salary|зарплат)", re.IGNORECASE)


def run_prefilter(text: str) -> PrefilterResult:
    normalized = text.strip()
    score = 0
    matched_positive: list[str] = []
    matched_negative: list[str] = []

    for pattern, weight in POSITIVE:
        if re.search(pattern, normalized, re.IGNORECASE):
            score += weight
            matched_positive.append(pattern)

    for pattern, weight in NEGATIVE:
        if re.search(pattern, normalized, re.IGNORECASE):
            score += weight
            matched_negative.append(pattern)

    if EMAIL_RE.search(normalized):
        score += 1
        matched_positive.append("meta:email")
    if TG_RE.search(normalized):
        score += 1
        matched_positive.append("meta:telegram")
    if SALARY_RE.search(normalized):
        score += 2
        matched_positive.append("meta:salary")

    accepted = score >= 3 and score > -4

    return {
        "accepted": accepted,
        "score": score,
        "matched_positive": matched_positive,
        "matched_negative": matched_negative,
    }
