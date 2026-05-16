import re
from typing import TypedDict


class JobClassificationResult(TypedDict):
    score: int
    confidence: float
    accepted: bool
    matched_positive: list[str]
    matched_negative: list[str]


POSITIVE_PATTERNS: list[tuple[str, int]] = [
    (r"\bhiring\b", 3),
    (r"\bvacanc(y|ies)\b", 4),
    (r"\blooking\s+for\b", 3),
    (r"\bdesigner\s+needed\b", 4),
    (r"\bremote\b", 2),
    (r"\bportfolio\b", 2),
    (r"\bcv\b", 2),
    (r"\bfull[- ]?time\b", 2),
    (r"\bfreelance\b", 3),
    (r"\b(intern(ship)?|стаж(ер|ировка))\b", 3),
    (r"\b(junior|middle|senior)\b", 2),
    (r"ищем", 4),
    (r"ваканси(я|и)", 4),
    (r"требуется", 3),
    (r"нужен", 2),
]

NEGATIVE_PATTERNS: list[tuple[str, int]] = [
    (r"\barticle\b", -3),
    (r"\bnews\b", -4),
    (r"\bpodcast\b", -4),
    (r"\binterview\b", -3),
    (r"\bwebinar\b", -4),
    (r"\bconference\b", -4),
    (r"\bopinion\b", -3),
    (r"\bcase\s+study\b", -3),
    (r"\bevent\b", -3),
    (r"\bmeetup\b", -4),
    (r"\bcourse\b", -3),
    (r"новост", -4),
    (r"подкаст", -4),
    (r"вебинар", -4),
    (r"конференц", -4),
    (r"интервью", -3),
    (r"мероприят", -3),
    (r"курс", -3),
]

CTA_PATTERNS = [
    r"\bapply\b",
    r"\bsend\s+cv\b",
    r"\bsend\s+portfolio\b",
    r"\bdm\b",
    r"\bcontact\b",
    r"отклик",
    r"присыла(йте|ть)",
    r"пишите",
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
TG_USERNAME_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{4,}")
SALARY_RE = re.compile(r"(\$|€|₽|руб\.?|k\b|тыс\.?|salary|зп|зарплат)", re.IGNORECASE)

ACCEPT_THRESHOLD = 5
STRONG_NEGATIVE_THRESHOLD = -5


def _find_matches(text: str, patterns: list[tuple[str, int]]) -> tuple[int, list[str]]:
    score = 0
    matches: list[str] = []
    for pattern, weight in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += weight
            matches.append(pattern)
    return score, matches


def calculate_job_score(text: str) -> int:
    result = classify_job_post_with_details(text)
    return result["score"]


def classify_job_post(text: str) -> bool:
    result = classify_job_post_with_details(text)
    return result["accepted"]


def classify_job_post_with_details(text: str) -> JobClassificationResult:
    normalized = text.strip()

    pos_score, matched_positive = _find_matches(normalized, POSITIVE_PATTERNS)
    neg_score, matched_negative = _find_matches(normalized, NEGATIVE_PATTERNS)

    meta_score = 0
    if EMAIL_RE.search(normalized):
        meta_score += 2
        matched_positive.append("meta:email")
    if TG_USERNAME_RE.search(normalized):
        meta_score += 1
        matched_positive.append("meta:telegram_username")
    if SALARY_RE.search(normalized):
        meta_score += 2
        matched_positive.append("meta:salary")
    if re.search(r"portfolio", normalized, re.IGNORECASE):
        meta_score += 2
        matched_positive.append("meta:portfolio_request")
    if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in CTA_PATTERNS):
        meta_score += 2
        matched_positive.append("meta:cta")

    score = pos_score + neg_score + meta_score

    # strong negative override
    if neg_score <= STRONG_NEGATIVE_THRESHOLD and pos_score < 5:
        accepted = False
    else:
        accepted = score >= ACCEPT_THRESHOLD

    confidence = max(0.0, min(1.0, (abs(score) / 12.0)))

    return {
        "score": score,
        "confidence": round(confidence, 2),
        "accepted": accepted,
        "matched_positive": matched_positive,
        "matched_negative": matched_negative,
    }
