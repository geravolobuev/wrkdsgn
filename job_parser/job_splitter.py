import json
import logging
import re

import requests

from job_parser.openrouter_client import OPENROUTER_URL, _model_chain

logger = logging.getLogger(__name__)

HEADER_PATTERNS = [
    r"вакансии недели",
    r"vacancies of the week",
    r"подборка вакансий",
]

ROLE_LINE_RE = re.compile(
    r"^(?:junior|middle|senior|lead|head|intern|стаж[её]р|младший)?\s*[a-zа-я0-9/+\- ]{3,}(designer|manager|director|редактор|дизайнер|менеджер)",
    re.IGNORECASE,
)


def _strip_headers(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        low = line.lower().strip()
        if any(re.search(p, low) for p in HEADER_PATTERNS):
            continue
        if low.startswith("разместить вакансию"):
            continue
        out.append(line)
    return out


def _deterministic_split(text: str) -> list[dict]:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    lines = _strip_headers(lines)
    chunks: list[list[str]] = []

    for line in lines:
        if ROLE_LINE_RE.search(line) and chunks:
            chunks.append([line])
        elif ROLE_LINE_RE.search(line):
            chunks.append([line])
        elif chunks:
            chunks[-1].append(line)

    if len(chunks) >= 2:
        return [{"raw_text": "\n".join(c).strip()} for c in chunks if "\n".join(c).strip()]

    return [{"raw_text": "\n".join(lines).strip() if lines else text.strip()}]


def split_jobs(text: str) -> list[dict]:
    deterministic = _deterministic_split(text)
    if len(deterministic) > 1:
        return deterministic

    api_key = __import__("os").getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return deterministic

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout_sec = int(__import__("os").getenv("OPENROUTER_TIMEOUT", "10"))
    short = text[:2600]
    prompt = (
        "Split this post into individual jobs if there are multiple vacancies. "
        "Return strict JSON only: {\"jobs\":[{\"raw_text\":\"...\"}]}. "
        "If only one job, return one item. Ignore digest headers."
        f"\nText:\n{short}"
    )

    for model in _model_chain():
        try:
            payload = {
                "model": model,
                "temperature": 0,
                "max_tokens": 420,
                "messages": [
                    {"role": "system", "content": "You return strict JSON only."},
                    {"role": "user", "content": prompt},
                ],
            }
            response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=timeout_sec)
            if response.status_code >= 400:
                continue
            content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = json.loads(content)
            jobs = parsed.get("jobs")
            if isinstance(jobs, list):
                clean: list[dict] = []
                for item in jobs:
                    if isinstance(item, dict) and isinstance(item.get("raw_text"), str):
                        raw = item["raw_text"].strip()
                        if raw:
                            clean.append({"raw_text": raw})
                if clean:
                    return clean
        except Exception as exc:
            logger.info("job_splitter fallback model=%s err=%s", model, exc)
            continue

    return deterministic
