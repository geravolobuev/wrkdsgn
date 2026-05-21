import json
import logging
import os
import re
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


def _validate_payload(parsed: Any) -> dict[str, Any] | None:
    if not isinstance(parsed, dict):
        return None

    required = {
        "is_ad",
        "is_job_post",
        "is_relevant",
        "role",
        "grade",
        "employment_type",
        "work_format",
        "reason_short",
    }
    if not required.issubset(parsed.keys()):
        return None

    if not isinstance(parsed.get("is_ad"), bool):
        return None
    if not isinstance(parsed.get("is_job_post"), bool):
        return None
    if not isinstance(parsed.get("is_relevant"), bool):
        return None

    allowed_roles = {
        "Graphic Designer",
        "Brand Designer",
        "Branding Specialist",
        "Motion Designer",
        "3D Designer",
        "Web Designer",
        "Art Director",
        "Creative Director",
        "Design Director",
        "Illustrator",
        "Type Designer",
        "Design Manager",
        "UI Designer",
    }
    allowed_grades = {"Junior", "Middle", "Senior", "Lead", "Head / Director", "Unknown"}
    allowed_employment = {"Full-time", "Part-time", "Contract", "Freelance", "Internship", "Unknown"}
    allowed_work = {"Remote", "Hybrid", "On-site", "Unknown"}

    role = _safe_enum(parsed.get("role"), allowed_roles)
    grade = _safe_enum(parsed.get("grade"), allowed_grades)
    employment_type = _safe_enum(parsed.get("employment_type"), allowed_employment)
    work_format = _safe_enum(parsed.get("work_format"), allowed_work)
    reason_short = _safe_text(parsed.get("reason_short"), 200)

    # For rejected posts role/grade may be null by prompt rules.
    if parsed["is_relevant"] and role is None:
        return None

    return {
        "is_ad": parsed["is_ad"],
        "is_job_post": parsed["is_job_post"],
        "is_relevant": parsed["is_relevant"],
        "role": role,
        "grade": grade,
        "employment_type": employment_type,
        "work_format": work_format,
        "reason_short": reason_short or "no_reason",
    }


def _contains_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _detect_role_from_text(raw_text: str) -> str | None:
    txt = raw_text.lower()
    rules: list[tuple[str, list[str]]] = [
        ("Design Director", [r"\bdesign director\b", r"директор[а-я\s-]*дизайн"]),
        ("Creative Director", [r"\bcreative director\b", r"креативн[а-я\s-]*директор"]),
        ("Art Director", [r"\bart[\s-]?director\b", r"арт[\s-]?директор"]),
        ("Motion Designer", [r"\bmotion designer\b", r"моушн[а-я\s-]*дизайнер", r"\bmotion\b"]),
        ("3D Designer", [r"\b3d\b", r"\b3d designer\b", r"3д"]),
        ("Illustrator", [r"\billustrator\b", r"иллюстратор"]),
        ("Type Designer", [r"\btype designer\b", r"типограф", r"шрифт"]),
        ("UI Designer", [r"\bui designer\b", r"\bui\b", r"интерфейс"]),
        ("Web Designer", [r"\bweb designer\b", r"веб[\s-]?дизайнер"]),
        ("Graphic Designer", [r"\bgraphic designer\b", r"графическ[а-я\s-]*дизайнер", r"коммуникационн[а-я\s-]*дизайнер"]),
        ("Design Manager", [r"\bdesign manager\b", r"дизайн[\s-]?менеджер"]),
        ("Branding Specialist", [r"\bbranding specialist\b", r"брендинг[\s-]?специалист"]),
        ("Brand Designer", [r"\bbrand designer\b", r"бренд[\s-]?дизайнер"]),
    ]
    for role, patterns in rules:
        if _contains_any(txt, patterns):
            return role
    return None


def _detect_employment_type(raw_text: str) -> str | None:
    txt = raw_text.lower()
    if _contains_any(txt, [r"стажир", r"\bintern(ship)?\b", r"#стажиров"]):
        return "Internship"
    if _contains_any(txt, [r"проектн", r"\bcontract\b", r"\bсрочн", r"\bсрок[а-я\s-]*\d+\s*[-–]?\s*\d*\s*месяц", r"смз", r"\bип\b"]):
        return "Contract"
    if _contains_any(txt, [r"\bfreelance\b", r"фриланс"]):
        return "Freelance"
    if _contains_any(txt, [r"\bpart[- ]?time\b", r"частичн[а-я\s-]*занятост"]):
        return "Part-time"
    if _contains_any(txt, [r"\bfull[- ]?time\b", r"полная занятость", r"30[-–]40\s*час"]):
        return "Full-time"
    return None


def _detect_work_format(raw_text: str) -> str | None:
    txt = raw_text.lower()
    has_remote = _contains_any(txt, [r"удален", r"\bremote\b"])
    has_hybrid = _contains_any(txt, [r"гибрид", r"\bhybrid\b"])
    has_office = _contains_any(txt, [r"офис", r"on[- ]?site", r"он[- ]?сайт"])
    if has_hybrid or (has_remote and has_office):
        return "Hybrid"
    if has_remote:
        return "Remote"
    if has_office:
        return "On-site"
    return None


def _apply_rule_overrides(validated: dict[str, Any], raw_text: str) -> dict[str, Any]:
    if not validated.get("is_relevant"):
        return validated

    role_from_text = _detect_role_from_text(raw_text)
    employment_from_text = _detect_employment_type(raw_text)
    work_format_from_text = _detect_work_format(raw_text)

    if role_from_text and role_from_text != validated.get("role"):
        logger.info("Override role via rules: %s -> %s", validated.get("role"), role_from_text)
        validated["role"] = role_from_text
    if employment_from_text and employment_from_text != validated.get("employment_type"):
        logger.info("Override employment_type via rules: %s -> %s", validated.get("employment_type"), employment_from_text)
        validated["employment_type"] = employment_from_text
    if work_format_from_text and work_format_from_text != validated.get("work_format"):
        logger.info("Override work_format via rules: %s -> %s", validated.get("work_format"), work_format_from_text)
        validated["work_format"] = work_format_from_text

    # Conservative seniority correction for internships.
    if validated.get("employment_type") == "Internship" and validated.get("grade") in {"Senior", "Lead", "Head / Director"}:
        logger.info("Override grade via rules: %s -> Unknown (internship signal)", validated.get("grade"))
        validated["grade"] = "Unknown"

    return validated


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
                    "max_tokens": 240,
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

                validated = _apply_rule_overrides(validated, raw_text)
                validated["selected_model"] = model
                logger.info("Enrichment success model=%s", model)
                return validated
            except (requests.RequestException, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
                logger.warning("Enrichment model=%s failed attempt=%s err=%s", model, attempt, exc)
                time.sleep(0.2)
                continue

    logger.warning("All enrichment models failed")
    return None
