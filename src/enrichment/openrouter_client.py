import json
import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from src.enrichment.taxonomy import (
    EMPLOYMENT_TYPES,
    LANGUAGES,
    LEVELS,
    REMOTE_TYPES,
    ROLE_TYPES,
    SEMANTIC_TAGS,
    SPECIALIZATIONS,
    TOOLS,
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_MODEL_FALLBACKS = [
    "meta-llama/llama-3.3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
]


@dataclass
class EnrichmentResult:
    is_job: bool
    country: str | None
    city: str | None
    remote_type: str | None
    employment_type: str | None
    level: str | None
    role_type: str | None
    specializations: list[str]
    semantic_tags: list[str]
    tools: list[str]
    language: list[str]
    salary_min: int | None
    salary_max: int | None


def _safe_enum(value: Any, allowed: list[str]) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if value in allowed else None


def _safe_array(values: Any, allowed: list[str]) -> list[str]:
    if not isinstance(values, list):
        return []
    uniq: list[str] = []
    seen = set()
    allowed_set = set(allowed)
    for item in values:
        if not isinstance(item, str):
            continue
        x = item.strip().lower()
        if x in allowed_set and x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = int(value)
        return v if v >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        v = int(value.strip())
        return v if v >= 0 else None
    return None


def _build_prompt(text: str) -> str:
    short = text[:2200]
    return (
        "Return STRICT JSON only. No markdown. No explanations. "
        "Use only enum values provided.\n"
        f"LEVELS={LEVELS}\n"
        f"SPECIALIZATIONS={SPECIALIZATIONS}\n"
        f"EMPLOYMENT_TYPES={EMPLOYMENT_TYPES}\n"
        f"REMOTE_TYPES={REMOTE_TYPES}\n"
        f"ROLE_TYPES={ROLE_TYPES}\n"
        f"SEMANTIC_TAGS={SEMANTIC_TAGS}\n"
        f"TOOLS={TOOLS}\n"
        f"LANGUAGES={LANGUAGES}\n"
        "Output schema keys: "
        "is_job,country,city,remote_type,employment_type,level,role_type,specializations,semantic_tags,tools,language,salary_min,salary_max.\n"
        "Unknown values -> null or [].\n"
        f"Vacancy text:\n{short}"
    )


def _parse_response(content: str) -> EnrichmentResult:
    parsed = json.loads(content)

    salary_min = _safe_int(parsed.get("salary_min"))
    salary_max = _safe_int(parsed.get("salary_max"))
    if salary_min is not None and salary_max is not None and salary_max < salary_min:
        salary_min, salary_max = salary_max, salary_min

    country = parsed.get("country") if isinstance(parsed.get("country"), str) else None
    city = parsed.get("city") if isinstance(parsed.get("city"), str) else None

    return EnrichmentResult(
        is_job=bool(parsed.get("is_job", True)),
        country=country.strip()[:80] if country else None,
        city=city.strip()[:80] if city else None,
        remote_type=_safe_enum(parsed.get("remote_type"), REMOTE_TYPES),
        employment_type=_safe_enum(parsed.get("employment_type"), EMPLOYMENT_TYPES),
        level=_safe_enum(parsed.get("level"), LEVELS),
        role_type=_safe_enum(parsed.get("role_type"), ROLE_TYPES),
        specializations=_safe_array(parsed.get("specializations"), SPECIALIZATIONS),
        semantic_tags=_safe_array(parsed.get("semantic_tags"), SEMANTIC_TAGS),
        tools=_safe_array(parsed.get("tools"), TOOLS),
        language=_safe_array(parsed.get("language"), LANGUAGES),
        salary_min=salary_min,
        salary_max=salary_max,
    )


def enrich_with_openrouter(text: str) -> EnrichmentResult | None:
    if os.getenv("ENABLE_AI_ENRICHMENT", "false").lower() != "true":
        return None

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None

    primary_model = os.getenv("OPENROUTER_MODEL", "").strip()
    models = [primary_model] if primary_model else []
    models.extend([m for m in DEFAULT_MODEL_FALLBACKS if m not in models])

    prompt = _build_prompt(text)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for model in models:
        for attempt in range(3):
            try:
                payload = {
                    "model": model,
                    "temperature": 0,
                    "max_tokens": 300,
                    "messages": [
                        {"role": "system", "content": "You are a strict JSON extraction engine."},
                        {"role": "user", "content": prompt},
                    ],
                }
                response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=35)
                if response.status_code == 429:
                    time.sleep(1.0 + attempt * 1.5)
                    continue
                response.raise_for_status()

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return _parse_response(content)
            except Exception:
                time.sleep(0.8 + attempt * 1.2)
                continue

    return None
