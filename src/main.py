import asyncio
import hashlib
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client
from telethon import TelegramClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from job_parser.openrouter_client import enrich_vacancy_with_ai

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
ENRICHMENT_VERSION = os.getenv("ENRICHMENT_VERSION", "v4_mvp_reset")

# Hard MVP scope: one channel only.
SOURCE_CHANNELS = ["@bbe_jobs"]


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


def extract_salary_range(text: str) -> tuple[int | None, int | None]:
    salary_context_re = re.compile(r"(зарп|зп|salary|usd|eur|руб|₽|\$|€|k\b|тыс)", re.IGNORECASE)
    if not salary_context_re.search(text):
        return None, None

    nums = re.findall(r"\d[\d\s]{2,}", text)
    values: list[int] = []
    for n in nums:
        digits = int(re.sub(r"\s+", "", n))
        if 10_000 <= digits <= 2_000_000_000:
            values.append(digits)
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], None
    return min(values), max(values)


def get_existing_by_hash(supabase: Client, content_hash: str) -> dict | None:
    res = supabase.table("vacancies").select("*").eq("content_hash", content_hash).limit(1).execute()
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


async def run() -> None:
    validate_env()
    supabase = make_supabase()

    logger.info("MVP scope channels=%s", SOURCE_CHANNELS)

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

        for source_channel in SOURCE_CHANNELS:
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

            for msg in messages:
                raw_text = msg.message.strip()
                if not raw_text:
                    continue

                content_hash = hashlib.sha256(f"{source_channel}:{msg.id}:{raw_text}".encode("utf-8")).hexdigest()

                existing = get_existing_by_hash(supabase, content_hash)
                if should_skip(existing, content_hash):
                    continue

                ai = await asyncio.to_thread(enrich_vacancy_with_ai, raw_text)
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
                salary_min, salary_max = extract_salary_range(raw_text)
                source_link = build_source_url(source_channel, msg.id)
                slug = slugify(f"{ai.get('role') or raw_title or 'job'}-{source_channel.strip('@')}-{msg.id}-{content_hash[:8]}")

                row = {
                    "source_channel": source_channel,
                    "source_message_id": msg.id,
                    "published_at": to_iso(msg.date) or datetime.now(timezone.utc).isoformat(),
                    "raw_text": raw_text,
                    "raw_title": raw_title,
                    "title": ai.get("role") or raw_title,
                    "canonical_title": ai.get("role"),
                    "display_title": ai.get("role"),
                    "description": raw_text,
                    "source_link": source_link,
                    "source_url": source_link,
                    "slug": slug,
                    "content_hash": content_hash,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
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
                else:
                    supabase.table("vacancies").upsert(row, on_conflict="content_hash", ignore_duplicates=True).execute()

                channel_saved += 1
                total_saved += 1

            total_processed += len(messages)
            logger.info("Channel summary %s: processed=%s saved=%s", source_channel, len(messages), channel_saved)

        logger.info(
            "Total summary: channels=%s processed=%s rejected=%s saved=%s",
            len(SOURCE_CHANNELS),
            total_processed,
            total_rejected,
            total_saved,
        )


if __name__ == "__main__":
    asyncio.run(run())
