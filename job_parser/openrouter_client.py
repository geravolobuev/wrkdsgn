import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OLLAMA_DEFAULT_URL = "https://ollama.com/api/chat"
OLLAMA_DEFAULT_MODEL = "gemma4:31b"
MODEL_FALLBACK_CHAIN = [
    "openai/gpt-oss-120b:free",
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


def _build_prompt(template: str, raw_text: str) -> str:
    truncated = raw_text[:3000]
    if "{{VACANCY_TEXT}}" in template:
        return template.replace("{{VACANCY_TEXT}}", truncated)
    # Backward-compatible mode: prompt file without explicit placeholder.
    return f"{template}\n\nVACANCY_TEXT:\n{truncated}"


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


def _extract_content_from_response(data: dict[str, Any]) -> str | None:
    # OpenAI/OpenRouter-like response.
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if isinstance(content, str):
        return content
    # Ollama /api/chat-like response.
    content = data.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    return None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    # 1) Direct JSON.
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    # 2) JSON inside fenced block.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        try:
            parsed = json.loads(fence.group(1))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass

    # 3) First {...} chunk.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        chunk = text[start : end + 1]
        try:
            parsed = json.loads(chunk)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _try_ollama(prompt: str, timeout_sec: int, max_retries: int) -> dict[str, Any] | None:
    model = os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL).strip() or OLLAMA_DEFAULT_MODEL
    url = os.getenv("OLLAMA_API_URL", OLLAMA_DEFAULT_URL).strip() or OLLAMA_DEFAULT_URL
    api_key = os.getenv("OLLAMA_API_KEY", "").strip()
    enabled = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
    if not enabled:
        return None

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "stream": False,
        "temperature": 0,
        "max_tokens": 240,
        "messages": [
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout_sec)
            if response.status_code >= 400:
                if response.status_code == 401:
                    logger.warning(
                        "Enrichment provider=ollama unauthorized url=%s model=%s hint=check OLLAMA_API_KEY and endpoint",
                        url,
                        model,
                    )
                logger.warning("Enrichment provider=ollama model=%s api_error=%s attempt=%s", model, response.status_code, attempt)
                continue

            content = _extract_content_from_response(response.json())
            if not isinstance(content, str):
                logger.warning("Enrichment provider=ollama model=%s empty_content attempt=%s", model, attempt)
                continue

            parsed = _extract_json_object(content)
            if parsed is None:
                logger.warning("Enrichment provider=ollama model=%s invalid_json_content", model)
                continue
            validated = _validate_payload(parsed)
            if validated is None:
                logger.warning("Enrichment provider=ollama model=%s invalid_schema", model)
                continue

            validated["selected_provider"] = "ollama"
            validated["selected_model"] = model
            logger.info("Enrichment success provider=ollama model=%s", model)
            return validated
        except (requests.RequestException, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Enrichment provider=ollama model=%s failed attempt=%s err=%s", model, attempt, exc)
            time.sleep(0.2)
            continue

    return None


def _try_openrouter(prompt: str, timeout_sec: int, max_retries: int, api_key: str) -> dict[str, Any] | None:
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
                    logger.warning("Enrichment provider=openrouter model=%s api_error=%s attempt=%s", model, response.status_code, attempt)
                    continue

                content = _extract_content_from_response(response.json())
                if not isinstance(content, str):
                    continue

                parsed = _extract_json_object(content)
                if parsed is None:
                    logger.warning("Enrichment provider=openrouter model=%s invalid_json_content", model)
                    continue
                validated = _validate_payload(parsed)
                if validated is None:
                    logger.warning("Enrichment provider=openrouter model=%s invalid_schema", model)
                    continue

                validated["selected_provider"] = "openrouter"
                validated["selected_model"] = model
                logger.info("Enrichment success provider=openrouter model=%s", model)
                return validated
            except (requests.RequestException, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
                logger.warning("Enrichment provider=openrouter model=%s failed attempt=%s err=%s", model, attempt, exc)
                time.sleep(0.2)
                continue

    return None


def enrich_vacancy_with_ai(raw_text: str) -> dict[str, Any] | None:
    if os.getenv("ENABLE_AI_ENRICHMENT", "true").lower() != "true":
        logger.info("AI enrichment disabled by ENABLE_AI_ENRICHMENT=false")
        return None

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    timeout_sec = int(os.getenv("OPENROUTER_TIMEOUT", "10"))
    max_retries = max(1, int(os.getenv("OPENROUTER_MAX_RETRIES", "1")))

    try:
        template = _read_prompt_template()
    except Exception as exc:
        logger.error("Cannot read prompt file: %s", exc)
        return None

    prompt = _build_prompt(template, raw_text)
    ollama_result = _try_ollama(prompt=prompt, timeout_sec=timeout_sec, max_retries=max_retries)
    if ollama_result is not None:
        return ollama_result

    if not openrouter_api_key:
        logger.warning("OLLAMA failed and OPENROUTER_API_KEY is not set; cannot continue enrichment")
        return None

    openrouter_result = _try_openrouter(prompt=prompt, timeout_sec=timeout_sec, max_retries=max_retries, api_key=openrouter_api_key)
    if openrouter_result is not None:
        return openrouter_result

    logger.warning("All enrichment models failed")
    return None
