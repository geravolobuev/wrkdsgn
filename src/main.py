import asyncio
import hashlib
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import Client, create_client
from telethon import TelegramClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from job_parser.embedding_client import get_text_embedding
from job_parser.openrouter_client import enrich_vacancy_with_ai
from job_parser.job_splitter import split_jobs_from_post

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

TG_API_ID = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_PHONE = os.getenv("TG_PHONE", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
TELETHON_SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "telegram_session")
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "30"))
AI_CONCURRENCY = max(1, int(os.getenv("AI_CONCURRENCY", "5")))
ENRICHMENT_VERSION = os.getenv("ENRICHMENT_VERSION", "v4_mvp_reset")

DEFAULT_SOURCE_CHANNELS = [
    "@designer_ru_work",
    "@designer_ru",
    "@designwork_vacansii",
    "@young_relocate",
    "@workinart",
    "@designbirzha",
    "@digital_rabota",
    "@wntddesign",
    "@vakansii_dizaynerov",
    "@designhunters",
    "@mirkreatorovjob",
    "@mnogovakansiy",
    "@designoffers",
    "@job_for_relocation",
    "@theblueprintcareer",
]


def parse_source_channels() -> list[str]:
    raw = os.getenv("SOURCE_CHANNELS", "").strip()
    if raw:
        channels = [item.strip() for item in raw.split(",") if item.strip()]
        if channels:
            return channels
    return list(DEFAULT_SOURCE_CHANNELS)


def validate_env() -> None:
    required = {
        "TG_API_ID": TG_API_ID,
        "TG_API_HASH": TG_API_HASH,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_SERVICE_ROLE_KEY,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    if os.getenv("ENABLE_AI_ENRICHMENT", "true").lower() != "true":
        raise RuntimeError("ENABLE_AI_ENRICHMENT must be true for current MVP pipeline")
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        raise RuntimeError("OPENROUTER_API_KEY is required for current MVP pipeline")


def make_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def to_iso(ts) -> str | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return cleaned[:90] if cleaned else "job"


def build_source_url(channel: str, message_id: int) -> str | None:
    if channel.startswith("@"):
        return f"https://t.me/{channel[1:]}/{message_id}"
    return None


def extract_raw_title(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0][:160] if lines else None


def make_dedupe_key(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"https?://\S+", " ", lowered)
    lowered = re.sub(r"@\w+", " ", lowered)
    lowered = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", " ", lowered)
    lowered = re.sub(r"[\d\W_]+", " ", lowered, flags=re.UNICODE)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    normalized = lowered[:1200]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_existing_by_hash(supabase: Client, content_hash: str) -> dict | None:
    res = supabase.table("vacancies").select("*").eq("content_hash", content_hash).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def get_existing_by_dedupe_key(supabase: Client, dedupe_key: str) -> dict | None:
    res = (
        supabase.table("vacancies")
        .select("*")
        .eq("dedupe_key", dedupe_key)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def should_skip(existing: dict | None, content_hash: str) -> bool:
    if not existing:
        return False
    return (
        existing.get("enriched_at") is not None
        and existing.get("enrichment_version") == ENRICHMENT_VERSION
        and existing.get("enrichment_hash") == content_hash
    )


def upsert_vacancy(supabase: Client, row: dict) -> None:
    try:
        supabase.table("vacancies").upsert(row, on_conflict="dedupe_key", ignore_duplicates=True).execute()
    except APIError as exc:
        payload = getattr(exc, "args", [None])[0]
        code = payload.get("code") if isinstance(payload, dict) else None
        message = payload.get("message") if isinstance(payload, dict) else str(exc)
        text = f"{code or ''} {message or ''}"
        if "42P10" in text or "no unique or exclusion constraint matching the ON CONFLICT specification" in text:
            logger.warning(
                "dedupe_key unique constraint missing in DB, fallback to content_hash upsert (apply migration 20260524_dedupe_key_unique_and_cleanup.sql)"
            )
            supabase.table("vacancies").upsert(row, on_conflict="content_hash", ignore_duplicates=True).execute()
            return
        raise


def get_vacancy_id(supabase: Client, content_hash: str) -> int | None:
    row = get_existing_by_hash(supabase, content_hash)
    if row and row.get("id") is not None:
        return int(row["id"])
    return None


def upsert_vacancy_embedding(supabase: Client, vacancy_id: int, source_text: str) -> None:
    embedding_payload = get_text_embedding(source_text)
    if embedding_payload is None:
        return
    embedding, embedding_model = embedding_payload
    try:
        supabase.table("vacancy_embeddings").upsert(
            {
                "vacancy_id": vacancy_id,
                "embedding_model": embedding_model,
                "embedding": embedding,
                "source_text": source_text[:2500],
            },
            on_conflict="vacancy_id",
            ignore_duplicates=False,
        ).execute()
    except APIError as exc:
        payload = getattr(exc, "args", [None])[0]
        code = payload.get("code") if isinstance(payload, dict) else None
        # Table/migration not yet applied: do not break scrape.
        if code in {"42P01", "42703"}:
            logger.warning("vacancy_embeddings table not ready, skip semantic indexing")
            return
        raise


async def run() -> None:
    validate_env()
    supabase = make_supabase()
    source_channels = parse_source_channels()

    logger.info("MVP scope channels=%s ai_concurrency=%s", source_channels, AI_CONCURRENCY)

    async with TelegramClient(TELETHON_SESSION_NAME, TG_API_ID, TG_API_HASH) as client:
        if not await client.is_user_authorized():
            if not TG_PHONE:
                raise RuntimeError("First run requires TG_PHONE to complete Telethon login")
            await client.send_code_request(TG_PHONE)
            code = input("Enter Telegram login code: ").strip()
            await client.sign_in(TG_PHONE, code)

        total_processed = 0
        total_rejected = 0
        total_saved = 0

        for source_channel in source_channels:
            try:
                source_entity = await client.get_entity(source_channel)
            except Exception as exc:
                logger.warning("Skip channel %s: cannot resolve (%s)", source_channel, exc)
                continue

            messages = []
            async for message in client.iter_messages(source_entity, limit=FETCH_LIMIT):
                if message.message:
                    messages.append(message)
            messages.reverse()

            channel_saved = 0
            sem = asyncio.Semaphore(AI_CONCURRENCY)

            async def enrich_candidate(msg, split_idx: int, split_text: str):
                raw_text = msg.message.strip()
                part_text = split_text.strip()
                if not raw_text or not part_text:
                    return {"status": "empty"}

                content_hash = hashlib.sha256(
                    f"{source_channel}:{msg.id}:{split_idx}:{part_text}".encode("utf-8")
                ).hexdigest()
                existing = get_existing_by_hash(supabase, content_hash)
                if should_skip(existing, content_hash):
                    return {"status": "skip"}
                dedupe_key = make_dedupe_key(part_text)
                existing_duplicate = get_existing_by_dedupe_key(supabase, dedupe_key)
                if existing_duplicate:
                    return {
                        "status": "dup",
                        "msg": msg,
                        "split_idx": split_idx,
                        "existing_duplicate_id": existing_duplicate.get("id"),
                        "existing_duplicate_channel": existing_duplicate.get("source_channel"),
                        "existing_duplicate_message_id": existing_duplicate.get("source_message_id"),
                    }

                async with sem:
                    ai = await asyncio.to_thread(enrich_vacancy_with_ai, part_text)

                return {
                    "status": "ok",
                    "msg": msg,
                    "raw_text": part_text,
                    "split_idx": split_idx,
                    "content_hash": content_hash,
                    "dedupe_key": dedupe_key,
                    "existing": existing,
                    "ai": ai,
                }

            tasks = []
            for msg in messages:
                if not msg.message:
                    continue
                split_parts = split_jobs_from_post(msg.message)
                if len(split_parts) > 1:
                    logger.info(
                        "Split post channel=%s message_id=%s chunks=%s",
                        source_channel,
                        msg.id,
                        len(split_parts),
                    )
                for split_idx, split_text in enumerate(split_parts):
                    tasks.append(asyncio.create_task(enrich_candidate(msg, split_idx, split_text)))

            for fut in asyncio.as_completed(tasks):
                result = await fut
                if result["status"] in {"empty", "skip"}:
                    continue
                if result["status"] == "dup":
                    logger.info(
                        "Duplicate skip channel=%s message_id=%s split_idx=%s existing_id=%s existing_source=%s/%s",
                        source_channel,
                        result["msg"].id,
                        result["split_idx"],
                        result.get("existing_duplicate_id"),
                        result.get("existing_duplicate_channel"),
                        result.get("existing_duplicate_message_id"),
                    )
                    continue

                msg = result["msg"]
                raw_text = result["raw_text"]
                split_idx = result["split_idx"]
                content_hash = result["content_hash"]
                dedupe_key = result["dedupe_key"]
                existing = result["existing"]
                ai = result["ai"]

                if ai is None:
                    total_rejected += 1
                    continue

                is_ad = bool(ai.get("is_ad"))
                is_job_post = bool(ai.get("is_job_post"))
                is_relevant = bool(ai.get("is_relevant"))
                is_job = (not is_ad) and is_job_post and is_relevant

                logger.info(
                    "AI filter channel=%s message_id=%s is_ad=%s is_job_post=%s is_relevant=%s is_job=%s",
                    source_channel,
                    msg.id,
                    is_ad,
                    is_job_post,
                    is_relevant,
                    is_job,
                )

                if not is_job:
                    total_rejected += 1
                    continue

                raw_title = extract_raw_title(raw_text)
                source_link = build_source_url(source_channel, msg.id)
                slug = slugify(
                    f"{ai.get('role') or raw_title or 'job'}-{source_channel.strip('@')}-{msg.id}-{split_idx}-{content_hash[:8]}"
                )

                row = {
                    "source_channel": source_channel,
                    "source_message_id": msg.id,
                    "published_at": to_iso(msg.date) or datetime.now(timezone.utc).isoformat(),
                    "raw_text": raw_text,
                    "title": ai.get("role") or raw_title,
                    "canonical_title": ai.get("role"),
                    "display_title": ai.get("role"),
                    "description": raw_text,
                    "source_link": source_link,
                    "slug": slug,
                    "content_hash": content_hash,
                    "dedupe_key": dedupe_key,
                    "is_job": True,
                    "filter_status": "accepted",
                    "filter_reason": ai.get("reason_short") or "ai_relevant",
                    "pipeline_stage": "enriched",
                    "seniority": ai.get("grade"),
                    "employment_type": ai.get("employment_type"),
                    "work_format": ai.get("work_format"),
                    "enriched_at": datetime.now(timezone.utc).isoformat(),
                    "enrichment_version": ENRICHMENT_VERSION,
                    "enrichment_hash": content_hash,
                }

                if existing:
                    supabase.table("vacancies").update(row).eq("id", existing["id"]).execute()
                    vacancy_id = int(existing["id"])
                else:
                    upsert_vacancy(supabase, row)
                    vacancy_id = get_vacancy_id(supabase, content_hash)
                if vacancy_id:
                    upsert_vacancy_embedding(supabase, vacancy_id, raw_text)

                channel_saved += 1
                total_saved += 1

            total_processed += len(messages)
            logger.info("Channel summary %s: processed=%s saved=%s", source_channel, len(messages), channel_saved)

        logger.info(
            "Total summary: channels=%s processed=%s rejected=%s saved=%s",
            len(source_channels),
            total_processed,
            total_rejected,
            total_saved,
        )


if __name__ == "__main__":
    asyncio.run(run())
