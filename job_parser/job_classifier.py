import re

POSITIVE_WEAK = [
    "вакансия",
    "вакансии",
    "ищем",
    "ищу",
    "hiring",
    "job",
    "open position",
    "portfolio",
    "портфолио",
    "cv",
    "resume",
    "резюме",
    "intern",
    "стаж",
]

POSITIVE_STRONG = [
    "full-time",
    "remote",
    "contract",
    "удален",
    "удалён",
]

NEGATIVE = [
    "курс",
    "обучение",
    "webinar",
    "регистрация",
    "сертификат",
    "заработок",
    "легкие деньги",
    "интенсив",
    "training program",
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
TG_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{4,}")
SALARY_RE = re.compile(r"(₽|\$|€)", re.IGNORECASE)


def _count_phrase(text: str, phrase: str) -> int:
    return 1 if phrase in text else 0


def job_score(text: str) -> int:
    normalized = text.lower()
    score = 0

    for phrase in POSITIVE_WEAK:
        if _count_phrase(normalized, phrase):
            score += 2

    for phrase in POSITIVE_STRONG:
        if _count_phrase(normalized, phrase):
            score += 3

    if SALARY_RE.search(text):
        score += 3

    if EMAIL_RE.search(text) or TG_RE.search(text):
        score += 2

    for phrase in NEGATIVE:
        if _count_phrase(normalized, phrase):
            score -= 3

    return score


def classify_job_or_ad_by_score(text: str) -> str:
    score = job_score(text)
    if score >= 3:
        return "JOB"
    if score <= 0:
        return "AD"
    return "UNCERTAIN"
