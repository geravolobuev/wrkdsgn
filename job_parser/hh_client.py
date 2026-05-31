from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)

HH_API_URL = "https://api.hh.ru/vacancies"
HH_SOURCE_CHANNEL = "hh.ru"
HH_PER_PAGE = 50


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _expand_query_groups(raw_queries: list[str]) -> list[str]:
    phrases: list[str] = []
    seen: set[str] = set()
    for group in raw_queries:
        for part in re.split(r"\s+OR\s+", group, flags=re.IGNORECASE):
            phrase = re.sub(r"\s+", " ", part).strip()
            lowered = phrase.lower()
            if not phrase or lowered in seen:
                continue
            seen.add(lowered)
            phrases.append(phrase)
    return phrases

HH_SEARCH_QUERIES = [
    "graphic designer OR visual designer OR brand designer OR communication designer OR marketing designer OR editorial designer OR packaging designer",
    "motion designer OR 3d designer OR motion graphics OR 3D artist",
    "web designer OR ui designer OR interface designer",
    "illustrator OR illustration OR type designer OR typography",
    "art director OR creative director OR design director OR design manager",
    "графический дизайнер OR визуальный дизайнер OR бренд дизайнер OR коммуникационный дизайнер OR маркетинг дизайнер OR дизайнер упаковки OR дизайнер презентаций",
    "моушен дизайнер OR 3D дизайнер OR 3D artist",
    "веб дизайнер OR ui дизайнер OR дизайнер интерфейсов",
    "иллюстратор OR типограф OR дизайнер шрифтов",
    "арт директор OR креативный директор OR дизайн директор OR руководитель дизайна",
]

HH_SEARCH_PHRASES = _expand_query_groups(HH_SEARCH_QUERIES)

REJECT_ROLE_PATTERNS = [
    r"\bux\b",
    r"\bux/ui\b",
    r"\bui/ux\b",
    r"ux designer",
    r"product designer",
    r"product manager",
    r"product owner",
    r"ux research",
    r"ux researcher",
    r"service design",
    r"service designer",
    r"researcher",
    r"research analyst",
    r"growth designer",
    r"growth manager",
    r"marketing manager",
    r"performance marketer",
    r"prompt engineer",
    r"developer",
    r"frontend",
    r"backend",
    r"fullstack",
    r"engineer",
    r"qa",
    r"devops",
    r"data scientist",
    r"analyst",
    r"аналитик",
    r"исследователь",
    r"исследован",
    r"продуктов",
    r"продакт",
    r"менеджер продукта",
    r"разработчик",
    r"инженер",
    r"ux-диз",
    r"ui/ux",
]

POSITIVE_VISUAL_PATTERNS = [
    r"graphic design",
    r"visual design",
    r"brand design",
    r"communication design",
    r"marketing design",
    r"editorial design",
    r"packaging",
    r"presentation",
    r"information design",
    r"key visual",
    r"motion",
    r"\b3d\b",
    r"web design",
    r"ui design",
    r"illustrat",
    r"typograph",
    r"art director",
    r"creative director",
    r"design director",
    r"design manager",
    r"графическ",
    r"визуальн",
    r"бренд",
    r"коммуникационн",
    r"маркетинг дизайнер",
    r"дизайн упаков",
    r"дизайн презента",
    r"моуш",
    r"веб-диз",
    r"веб дизай",
    r"интерфейс",
    r"иллюстратор",
    r"типограф",
    r"арт-дир",
    r"креативн директор",
    r"дизайн директор",
    r"руководител[ья] дизайна",
]

EXECUTION_PATTERNS = [
    r"\bfigma\b",
    r"\bphotoshop\b",
    r"\billustrator\b",
    r"\bindesign\b",
    r"\bafter effects\b",
    r"\bblender\b",
    r"\bcinema ?4d\b",
    r"\bpowerpoint\b",
    r"\bkeynote\b",
    r"\bretouch",
    r"\blayout",
    r"\bvisuals?\b",
    r"\bbranding\b",
    r"\bidentity\b",
    r"\bposter",
    r"\bbanner",
    r"\bdeck",
    r"\bprint",
    r"\bpackaging\b",
    r"\billustration\b",
    r"\banimation\b",
    r"\b3d\b",
    r"\bdesign system\b",
    r"\bгайд",
    r"\bмакет",
    r"\bвизуал",
    r"\bбаннер",
    r"\bпрезента",
    r"\bупаков",
    r"\bиллюстрац",
    r"\bанимац",
    r"\bретуш",
]

NON_EXECUTION_PATTERNS = [
    r"without design execution",
    r"research only",
    r"analytics only",
    r"strategy only",
    r"без визуального дизайна",
    r"без дизайн задач",
    r"только аналитика",
    r"только исследован",
    r"только стратегия",
]


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _parse_hh_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _salary_text(payload: dict[str, Any]) -> str | None:
    salary = payload.get("salary")
    if not isinstance(salary, dict):
        return None
    parts: list[str] = []
    if salary.get("from") is not None:
        parts.append(f"from {salary['from']}")
    if salary.get("to") is not None:
        parts.append(f"to {salary['to']}")
    currency = salary.get("currency")
    if currency:
        parts.append(str(currency))
    return " ".join(parts) if parts else None


def _snippet_text(payload: dict[str, Any], key: str) -> str | None:
    snippet = payload.get("snippet")
    if not isinstance(snippet, dict):
        return None
    value = snippet.get(key)
    if not isinstance(value, str):
        return None
    return re.sub(r"<[^>]+>", " ", value)


def _professional_roles(payload: dict[str, Any]) -> str | None:
    roles = payload.get("professional_roles")
    if not isinstance(roles, list):
        return None
    names = [role.get("name") for role in roles if isinstance(role, dict) and isinstance(role.get("name"), str)]
    return ", ".join(names) if names else None


def normalize_hh_vacancy(payload: dict[str, Any]) -> dict[str, Any]:
    title = _clean_text(payload.get("name"))
    employer = payload.get("employer") or {}
    employer_name = _clean_text(employer.get("name")) if isinstance(employer, dict) else ""
    area = payload.get("area") or {}
    area_name = _clean_text(area.get("name")) if isinstance(area, dict) else ""
    employment = payload.get("employment") or {}
    employment_name = _clean_text(employment.get("name")) if isinstance(employment, dict) else ""
    schedule = payload.get("schedule") or {}
    schedule_name = _clean_text(schedule.get("name")) if isinstance(schedule, dict) else ""
    experience = payload.get("experience") or {}
    experience_name = _clean_text(experience.get("name")) if isinstance(experience, dict) else ""
    salary_text = _salary_text(payload)
    role_text = _professional_roles(payload)
    requirement = _clean_text(_snippet_text(payload, "requirement"))
    responsibility = _clean_text(_snippet_text(payload, "responsibility"))

    parts = [
        title,
        f"Company: {employer_name}" if employer_name else "",
        f"Location: {area_name}" if area_name else "",
        f"Employment: {employment_name}" if employment_name else "",
        f"Schedule: {schedule_name}" if schedule_name else "",
        f"Experience: {experience_name}" if experience_name else "",
        f"Salary: {salary_text}" if salary_text else "",
        f"Professional roles: {role_text}" if role_text else "",
        f"Requirements: {requirement}" if requirement else "",
        f"Responsibilities: {responsibility}" if responsibility else "",
    ]
    raw_text = "\n".join(part for part in parts if part)

    return {
        "source_channel": HH_SOURCE_CHANNEL,
        "source_message_id": int(payload["id"]),
        "source_link": payload.get("alternate_url"),
        "published_at": _parse_hh_datetime(payload.get("published_at")),
        "raw_title": title or None,
        "raw_text": raw_text[:5000],
        "company": employer_name or None,
        "payload": payload,
    }


def hh_rejection_reason(candidate: dict[str, Any]) -> str | None:
    raw_title = candidate.get("raw_title") or ""
    raw_text = candidate.get("raw_text") or ""
    haystack = f"{raw_title}\n{raw_text}".lower()

    for pattern in REJECT_ROLE_PATTERNS:
        if re.search(pattern, haystack, flags=re.IGNORECASE):
            return f"reject_pattern:{pattern}"

    has_visual_signal = any(re.search(pattern, haystack, flags=re.IGNORECASE) for pattern in POSITIVE_VISUAL_PATTERNS)
    if not has_visual_signal:
        return "missing_visual_design_signal"

    has_execution_signal = any(re.search(pattern, haystack, flags=re.IGNORECASE) for pattern in EXECUTION_PATTERNS)
    has_non_execution_signal = any(re.search(pattern, haystack, flags=re.IGNORECASE) for pattern in NON_EXECUTION_PATTERNS)
    if has_non_execution_signal and not has_execution_signal:
        return "non_execution_design_role"

    return None


def _fetch_hh_page(
    *,
    query: str,
    page: int,
    per_page: int,
    timeout: int,
    user_agent: str,
) -> list[dict[str, Any]]:
    params = {
        "text": query,
        "page": page,
        "per_page": per_page,
        "only_with_salary": "false",
        "host": "hh.ru",
        "locale": "RU",
        "search_field": "name",
    }
    response = requests.get(
        HH_API_URL,
        params=params,
        timeout=timeout,
        headers={
            "HH-User-Agent": user_agent,
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
    )
    if response.status_code >= 400:
        body_preview = response.text[:400].replace("\n", " ")
        logger.warning(
            "HH fetch error status=%s query=%s page=%s body=%s",
            response.status_code,
            query,
            page,
            body_preview,
        )
    response.raise_for_status()
    data = response.json()
    items = data.get("items")
    if not isinstance(items, list):
        return []
    logger.info("HH query=%s page=%s items=%s", query, page, len(items))
    return [item for item in items if isinstance(item, dict) and item.get("id")]


def _fetch_hh_query(
    *,
    query: str,
    max_pages: int,
    per_page: int,
    timeout: int,
    user_agent: str,
    request_pause_seconds: float,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for page in range(max_pages):
        items = _fetch_hh_page(
            query=query,
            page=page,
            per_page=per_page,
            timeout=timeout,
            user_agent=user_agent,
        )
        if not items:
            break
        collected.extend(items)
        if len(items) < per_page:
            break
        if request_pause_seconds > 0:
            time.sleep(request_pause_seconds)
    return collected


def fetch_hh_vacancies() -> list[dict[str, Any]]:
    if os.getenv("HH_ENABLED", "false").lower() != "true":
        return []

    max_pages = max(1, _env_int("HH_MAX_PAGES", 10))
    per_page = min(HH_PER_PAGE, max(1, _env_int("HH_PER_PAGE", HH_PER_PAGE)))
    max_workers = max(1, _env_int("HH_MAX_WORKERS", 4))
    user_agent = os.getenv("HH_USER_AGENT", "wrkdsgn/1.0 (hello@wrkdsgn.vercel.app)")
    timeout = _env_int("HH_TIMEOUT", 20)
    request_pause_seconds = max(0.0, _env_float("HH_REQUEST_PAUSE_SECONDS", 0.3))

    logger.info(
        "HH config phrases=%s max_pages=%s per_page=%s max_workers=%s timeout=%s pause=%s",
        len(HH_SEARCH_PHRASES),
        max_pages,
        per_page,
        max_workers,
        timeout,
        request_pause_seconds,
    )

    unique: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _fetch_hh_query,
                query=query,
                max_pages=max_pages,
                per_page=per_page,
                timeout=timeout,
                user_agent=user_agent,
                request_pause_seconds=request_pause_seconds,
            )
            for query in HH_SEARCH_PHRASES
        ]
        for future in as_completed(futures):
            try:
                for payload in future.result():
                    vacancy_id = int(payload["id"])
                    if vacancy_id not in unique:
                        unique[vacancy_id] = normalize_hh_vacancy(payload)
            except requests.RequestException as exc:
                logger.warning("HH fetch failed: %s", exc)

    filtered: list[dict[str, Any]] = []
    rejected = 0
    for candidate in unique.values():
        reason = hh_rejection_reason(candidate)
        if reason:
            rejected += 1
            logger.info("HH reject vacancy_id=%s reason=%s", candidate["source_message_id"], reason)
            continue
        filtered.append(candidate)

    logger.info("HH fetch summary unique=%s accepted=%s rejected=%s", len(unique), len(filtered), rejected)
    return filtered
