import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_FALLBACK_CHAIN = [
    "meta-llama/llama-3.3-8b-instruct:free",
    "qwen/qwen-2.5-7b-instruct:free",
    "google/gemma-2-9b-it:free",
]
OPTIONAL_GENERIC_FALLBACK = "openrouter/free"

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[1] / "job-enrichment.prompt.txt"


def _model_chain() -> list[str]:
    chain = list(MODEL_FALLBACK_CHAIN)
    include_generic = os.getenv("OPENROUTER_INCLUDE_GENERIC_FALLBACK", "true").lower() == "true"
    if include_generic and OPTIONAL_GENERIC_FALLBACK not in chain:
        chain.append(OPTIONAL_GENERIC_FALLBACK)
    return chain


def _read_prompt_template() -> str:
    prompt_path = Path(os.getenv("JOB_ENRICHMENT_PROMPT_PATH", str(DEFAULT_PROMPT_PATH)))
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def _safe_text(value: Any, max_len: int = 120) -> str | None:
    if not isinstance(value, str):
        return None
    clean = value.strip()
    return clean[:max_len] if clean else None


def _safe_enum(value: Any, allowed: set[str]) -> str | None:
    if not isinstance(value, str):
        return None
    val = value.strip()
    return val if val in allowed else None


def _safe_array(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        if isinstance(item, str):
            clean = item.strip()
            if clean and clean not in out:
                out.append(clean[:64])
    return out[:10]


def _safe_confidence(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        if v < 0:
            return 0.0
        if v > 1:
            return 1.0
        return round(v, 3)
    return None


def _validate_payload(parsed: Any) -> dict[str, Any] | None:
    if not isinstance(parsed, dict):
        return None

    required = {
        "canonical_title",
        "display_title",
        "seniority",
        "employment_type",
        "work_format",
        "country",
        "city",
        "system_tags",
        "ai_keywords",
        "industry",
        "company_type",
        "company_name",
        "confidence_score",
    }
    if not required.issubset(parsed.keys()):
        return None

    allowed_titles = {
        "Product Designer", "Graphic Designer", "Brand Designer", "Motion Designer", "3D Designer",
        "UX/UI Designer", "Web Designer", "Art Director", "Creative Director", "Design Director",
        "Illustrator", "Type Designer", "Design Researcher", "Design Manager",
    }
    allowed_seniority = {"Intern", "Junior", "Middle", "Senior", "Lead", "Head"}
    allowed_employment = {"Full-time", "Part-time", "Project"}
    allowed_work = {"Remote", "Hybrid", "Onsite"}
    allowed_industry = {
        "fintech", "saas", "ai", "fashion", "beauty", "gaming", "crypto", "ecommerce",
        "media", "telecom", "education", "healthcare", "music", "sports",
    }
    allowed_company_type = {"startup", "corporation", "agency"}

    return {
        "canonical_title": _safe_enum(parsed.get("canonical_title"), allowed_titles),
        "display_title": _safe_text(parsed.get("display_title"), 60),
        "seniority": _safe_enum(parsed.get("seniority"), allowed_seniority),
        "employment_type": _safe_enum(parsed.get("employment_type"), allowed_employment),
        "work_format": _safe_enum(parsed.get("work_format"), allowed_work),
        "country": _safe_text(parsed.get("country"), 80),
        "city": _safe_text(parsed.get("city"), 80),
        "system_tags": _safe_array(parsed.get("system_tags")),
        "ai_keywords": _safe_array(parsed.get("ai_keywords")),
        "industry": _safe_enum(parsed.get("industry"), allowed_industry),
        "company_type": _safe_enum(parsed.get("company_type"), allowed_company_type),
        "company_name": _safe_text(parsed.get("company_name"), 120),
        "confidence_score": _safe_confidence(parsed.get("confidence_score")),
    }


def enrich_vacancy_with_ai(raw_text: str) -> dict[str, Any] | None:
    if os.getenv("ENABLE_AI_ENRICHMENT", "true").lower() != "true":
        logger.info("AI enrichment disabled by ENABLE_AI_ENRICHMENT=false")
        return None

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        logger.warning("OPENROUTER_API_KEY is not set; skipping enrichment")
        return None

    timeout_sec = int(os.getenv("OPENROUTER_TIMEOUT", "10"))
    max_retries = max(1, int(os.getenv("OPENROUTER_MAX_RETRIES", "1")))

    try:
        template = _read_prompt_template()
    except Exception as exc:
        logger.error("Cannot read prompt file: %s", exc)
        return None

    prompt = template.replace("{{VACANCY_TEXT}}", raw_text[:3000])
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for model in _model_chain():
        for attempt in range(1, max_retries + 1):
            try:
                payload = {
                    "model": model,
                    "temperature": 0,
                    "max_tokens": 420,
                    "messages": [
                        {"role": "system", "content": "Return strict JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                }
                response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=timeout_sec)
                if response.status_code >= 400:
                    logger.warning("Enrichment model=%s api_error=%s attempt=%s", model, response.status_code, attempt)
                    continue

                content = response.json().get("choices", [{}])[0].get("message", {}).get("content")
                if not isinstance(content, str):
                    continue

                parsed = json.loads(content)
                validated = _validate_payload(parsed)
                if validated is None:
                    logger.warning("Enrichment model=%s invalid_schema", model)
                    continue

                logger.info("Enrichment success model=%s", model)
                return validated
            except (requests.RequestException, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
                logger.warning("Enrichment model=%s failed attempt=%s err=%s", model, attempt, exc)
                time.sleep(0.2)
                continue

    logger.warning("All enrichment models failed")
    return None
