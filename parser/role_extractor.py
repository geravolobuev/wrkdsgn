import json
import logging

import requests

from parser.openrouter_client import OPENROUTER_URL, _model_chain

logger = logging.getLogger(__name__)

ROLE_KEYWORDS = [
    "smm manager",
    "product designer",
    "ux designer",
    "ui designer",
    "graphic designer",
    "motion designer",
    "art director",
    "creative director",
    "content creator",
    "video editor",
    "reels maker",
    "illustrator",
    "web designer",
]


def _heuristic_role(text: str) -> str:
    low = text.lower()
    for role in ROLE_KEYWORDS:
        if role in low:
            return role.title()

    if "reels" in low or "shorts" in low or "tiktok" in low:
        if "монтаж" in low or "editing" in low:
            return "Video Editor"
        return "Content Creator"

    return "Unknown Role"


def extract_canonical_role(text: str) -> str:
    api_key = __import__("os").getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return _heuristic_role(text)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout_sec = int(__import__("os").getenv("OPENROUTER_TIMEOUT", "10"))
    short = text[:1800]
    prompt = (
        "Extract canonical profession title from the vacancy text. "
        "Return JSON only: {\"canonical_title\": \"...\"}. "
        "Use short noun phrase (2-5 words), no marketing wording, no sentence copy."
        f"\nText:\n{short}"
    )

    for model in _model_chain():
        try:
            payload = {
                "model": model,
                "temperature": 0,
                "max_tokens": 40,
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
            value = parsed.get("canonical_title")
            if isinstance(value, str) and value.strip():
                return value.strip()[:80]
        except Exception as exc:
            logger.info("role_extractor fallback model=%s err=%s", model, exc)
            continue

    return _heuristic_role(text)
