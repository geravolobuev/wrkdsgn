import json
import logging
import os
import time
from typing import Any

import requests

from parser.deterministic_prefilter import run_prefilter
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

MODEL_FALLBACK_CHAIN = [
    "meta-llama/llama-3.3-8b-instruct:free",
    "qwen/qwen-2.5-7b-instruct:free",
    "google/gemma-2-9b-it:free",
]
OPTIONAL_GENERIC_FALLBACK = "openrouter/free"

logger = logging.getLogger(__name__)


def _safe_enum(value: Any, allowed: list[str]) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in set(allowed) else None


def _safe_array(values: Any, allowed: list[str]) -> list[str]:
    if not isinstance(values, list):
        return []

    allowed_set = set(allowed)
    seen: set[str] = set()
    clean: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        normalized = item.strip().lower()
        if normalized in allowed_set and normalized not in seen:
            seen.add(normalized)
            clean.append(normalized)
    return clean


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        x = int(value)
        return x if x >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        x = int(value.strip())
        return x if x >= 0 else None
    return None


def _deterministic_fallback(text: str) -> dict[str, Any]:
    pre = run_prefilter(text)
    return {
        "is_job": bool(pre.get("accepted", False)),
        "level": "unknown",
        "specializations": [],
        "city": None,
        "country": None,
        "remote_type": None,
    }


def _build_prompt(text: str) -> str:
    short_text = text[:2500]
    return (
        "Return STRICT JSON only. No markdown. No explanations. No extra text.\n"
        "If unknown, use null or empty array.\n"
        f"Allowed enums: LEVELS={LEVELS}, SPECIALIZATIONS={SPECIALIZATIONS}, "
        f"EMPLOYMENT_TYPES={EMPLOYMENT_TYPES}, REMOTE_TYPES={REMOTE_TYPES}, "
        f"ROLE_TYPES={ROLE_TYPES}, SEMANTIC_TAGS={SEMANTIC_TAGS}, TOOLS={TOOLS}, LANGUAGES={LANGUAGES}.\n"
        "Required keys: is_job, level, specializations.\n"
        "Optional keys: country, city, remote_type, employment_type, role_type, semantic_tags, tools, language, salary_min, salary_max.\n"
        f"Vacancy text:\n{short_text}"
    )


def _reject_markdown_or_text(raw: str) -> bool:
    stripped = raw.strip()
    if "```" in stripped:
        return True
    if not stripped.startswith("{") or not stripped.endswith("}"):
        return True
    return False


def _validate_and_normalize_payload(parsed: Any) -> dict[str, Any] | None:
    if not isinstance(parsed, dict):
        return None

    if not isinstance(parsed.get("is_job"), bool):
        return None

    level = parsed.get("level")
    if level is not None and not isinstance(level, str):
        return None

    if not isinstance(parsed.get("specializations"), list):
        return None

    salary_min = _safe_int(parsed.get("salary_min"))
    salary_max = _safe_int(parsed.get("salary_max"))
    if salary_min is not None and salary_max is not None and salary_max < salary_min:
        salary_min, salary_max = salary_max, salary_min

    country = parsed.get("country") if isinstance(parsed.get("country"), str) else None
    city = parsed.get("city") if isinstance(parsed.get("city"), str) else None

    normalized = {
        "is_job": parsed["is_job"],
        "country": country.strip()[:80] if country else None,
        "city": city.strip()[:80] if city else None,
        "remote_type": _safe_enum(parsed.get("remote_type"), REMOTE_TYPES),
        "employment_type": _safe_enum(parsed.get("employment_type"), EMPLOYMENT_TYPES),
        "level": _safe_enum(level, LEVELS) if level is not None else None,
        "role_type": _safe_enum(parsed.get("role_type"), ROLE_TYPES),
        "specializations": _safe_array(parsed.get("specializations"), SPECIALIZATIONS),
        "semantic_tags": _safe_array(parsed.get("semantic_tags"), SEMANTIC_TAGS),
        "tools": _safe_array(parsed.get("tools"), TOOLS),
        "language": _safe_array(parsed.get("language"), LANGUAGES),
        "salary_min": salary_min,
        "salary_max": salary_max,
    }
    return normalized


def _model_chain() -> list[str]:
    chain = list(MODEL_FALLBACK_CHAIN)
    include_generic = os.getenv("OPENROUTER_INCLUDE_GENERIC_FALLBACK", "true").lower() == "true"
    if include_generic and OPTIONAL_GENERIC_FALLBACK not in chain:
        chain.append(OPTIONAL_GENERIC_FALLBACK)
    return chain


def enrich_vacancy_with_ai(text: str) -> dict[str, Any] | None:
    if os.getenv("ENABLE_AI_ENRICHMENT", "true").lower() != "true":
        logger.info("AI enrichment disabled by ENABLE_AI_ENRICHMENT=false")
        return None

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        logger.warning("OPENROUTER_API_KEY is not set; skipping AI enrichment")
        return None

    timeout_sec = int(os.getenv("OPENROUTER_TIMEOUT", "10"))
    max_retries = max(1, int(os.getenv("OPENROUTER_MAX_RETRIES", "1")))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    prompt = _build_prompt(text)

    for model in _model_chain():
        logger.info("OpenRouter: trying model=%s", model)

        for attempt in range(1, max_retries + 1):
            try:
                payload = {
                    "model": model,
                    "temperature": 0,
                    "max_tokens": 260,
                    "messages": [
                        {"role": "system", "content": "You are a strict JSON extraction engine."},
                        {"role": "user", "content": prompt},
                    ],
                }
                response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=timeout_sec)

                if response.status_code >= 400:
                    logger.warning(
                        "OpenRouter: model=%s failed (api_error status=%s attempt=%s/%s)",
                        model,
                        response.status_code,
                        attempt,
                        max_retries,
                    )
                    continue

                data = response.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )

                if not isinstance(content, str) or _reject_markdown_or_text(content):
                    logger.warning("OpenRouter: model=%s rejected (invalid_json_format)", model)
                    continue

                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    logger.warning("OpenRouter: model=%s rejected (invalid_json_parse)", model)
                    continue

                validated = _validate_and_normalize_payload(parsed)
                if validated is None:
                    logger.warning("OpenRouter: model=%s rejected (schema_validation_failed)", model)
                    continue

                logger.info("OpenRouter: model=%s success", model)
                logger.info("OpenRouter: final_selected_model=%s", model)
                return validated

            except requests.Timeout:
                logger.warning(
                    "OpenRouter: model=%s failed (timeout attempt=%s/%s)",
                    model,
                    attempt,
                    max_retries,
                )
            except requests.RequestException as exc:
                logger.warning(
                    "OpenRouter: model=%s failed (request_exception=%s attempt=%s/%s)",
                    model,
                    str(exc),
                    attempt,
                    max_retries,
                )
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning(
                    "OpenRouter: model=%s failed (invalid_response=%s attempt=%s/%s)",
                    model,
                    str(exc),
                    attempt,
                    max_retries,
                )

            time.sleep(0.25)

        logger.info("OpenRouter: fallback to next model after model=%s", model)

    fallback = _deterministic_fallback(text)
    logger.warning("OpenRouter: all models failed; deterministic_fallback_used")
    logger.info("OpenRouter: final_selected_model=deterministic_fallback")
    return fallback


def classify_uncertain_job_ad(text: str) -> str | None:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None

    timeout_sec = int(os.getenv("OPENROUTER_TIMEOUT", "10"))
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    prompt = (
        "You are a strict classifier. Determine if this post is a real job vacancy or an advertisement/funnel.\n"
        "Return only:\nJOB or AD\n"
        f"Text:\n{text[:1800]}"
    )

    for model in _model_chain():
        try:
            payload = {
                "model": model,
                "temperature": 0,
                "max_tokens": 4,
                "messages": [
                    {"role": "system", "content": "Return exactly one token: JOB or AD."},
                    {"role": "user", "content": prompt},
                ],
            }
            response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=timeout_sec)
            if response.status_code >= 400:
                continue
            content = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                .upper()
            )
            if content in {"JOB", "AD"}:
                return content
        except Exception:
            continue
    return None
