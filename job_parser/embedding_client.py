import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
EMBEDDING_MODEL_PRIMARY = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
EMBEDDING_MODEL_FALLBACK = "nomic-ai/nomic-embed-text-v1.5"


def _models() -> list[str]:
    primary = os.getenv("EMBEDDING_MODEL_PRIMARY", EMBEDDING_MODEL_PRIMARY).strip() or EMBEDDING_MODEL_PRIMARY
    fallback = os.getenv("EMBEDDING_MODEL_FALLBACK", EMBEDDING_MODEL_FALLBACK).strip() or EMBEDDING_MODEL_FALLBACK
    out = [primary]
    if fallback and fallback != primary:
        out.append(fallback)
    return out


def get_text_embedding(text: str) -> tuple[list[float], str] | None:
    if os.getenv("ENABLE_SEMANTIC_SEARCH", "false").lower() != "true":
        return None

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        logger.warning("Semantic search enabled but OPENROUTER_API_KEY missing")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    timeout_sec = int(os.getenv("EMBEDDING_TIMEOUT", "15"))
    max_chars = int(os.getenv("EMBEDDING_TEXT_MAX_CHARS", "2500"))
    input_text = text[:max_chars]

    for model in _models():
        try:
            payload = {
                "model": model,
                "input": input_text,
                "encoding_format": "float",
            }
            response = requests.post(OPENROUTER_EMBEDDINGS_URL, json=payload, headers=headers, timeout=timeout_sec)
            if response.status_code >= 400:
                logger.warning("Embedding model=%s api_error=%s", model, response.status_code)
                continue

            data: dict[str, Any] = response.json()
            arr = data.get("data") or []
            if not arr:
                continue
            emb = arr[0].get("embedding")
            if not isinstance(emb, list) or not emb:
                continue
            if not all(isinstance(x, (float, int)) for x in emb):
                continue
            return [float(x) for x in emb], model
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            logger.warning("Embedding model=%s failed err=%s", model, exc)
            continue
    return None

