import re

REMOTE_KEYWORDS = ["remote", "удален", "удалён"]
HYBRID_KEYWORDS = ["hybrid", "гибрид"]
ONSITE_KEYWORDS = ["onsite", "офис"]

CITY_PATTERNS = [
    r"\bberlin\b",
    r"\blondon\b",
    r"\bmoscow\b",
    r"\bмосква\b",
    r"\bекатеринбург\b",
    r"\byerevan\b",
]

COUNTRY_PATTERNS = [
    r"\bgermany\b",
    r"\buk\b",
    r"\brussia\b",
    r"\bросси[яи]\b",
    r"\barmenia\b",
    r"\beurope\b",
]


def extract_location(text: str) -> dict:
    low = text.lower()

    remote_type = None
    if any(k in low for k in REMOTE_KEYWORDS):
        remote_type = "remote"
    elif any(k in low for k in HYBRID_KEYWORDS):
        remote_type = "hybrid"
    elif any(k in low for k in ONSITE_KEYWORDS):
        remote_type = "onsite"

    city = None
    for pattern in CITY_PATTERNS:
        m = re.search(pattern, low)
        if m:
            city = m.group(0)
            break

    country = None
    for pattern in COUNTRY_PATTERNS:
        m = re.search(pattern, low)
        if m:
            country = m.group(0)
            break

    if city:
        city = city.strip().title()
    if country:
        country = country.strip().title()

    if "remote europe" in low:
        remote_type = "remote"
        country = "Europe"

    return {
        "city": city,
        "country": country,
        "remote_type": remote_type,
    }
