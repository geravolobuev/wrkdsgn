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

from job_parser.ad_classifier import is_ad_or_funnel
from job_parser.job_classifier import classify_job_or_ad_by_score, job_score
from job_parser.openrouter_client import enrich_vacancy_with_ai

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

TG_API_ID = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_PHONE = os.getenv("TG_PHONE", "")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "")
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
TELETHON_SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "telegram_session")
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "30"))
ENRICHMENT_VERSION = os.getenv("ENRICHMENT_VERSION", "v3_structured")


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

    if not SOURCE_CHANNEL and not SOURCE_CHANNELS:
        raise RuntimeError("Set SOURCE_CHANNELS (preferred) or SOURCE_CHANNEL")


def make_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def normalize_channel(value: str) -> str:
    channel = value.strip()
    if channel.startswith("https://t.me/"):
        channel = "@" + channel.split("https://t.me/", 1)[1].strip("/")
    return channel


def get_source_channels() -> list[str]:
    raw = SOURCE_CHANNELS.strip() if SOURCE_CHANNELS.strip() else SOURCE_CHANNEL.strip()
    raw = raw.replace("\n", ",")

    channels: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        if not item.strip():
            continue
        ch = normalize_channel(item)
        if ch not in seen:
            seen.add(ch)
            channels.append(ch)

    if not channels:
        raise RuntimeError("No valid channels in SOURCE_CHANNELS/SOURCE_CHANNEL")

    return channels


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
    salary_context_re = re.compile(
        r"(зарп|зп|salary|usd|eur|руб|₽|\$|€|k\b|тыс)",
        re.IGNORECASE,
    )
    if not salary_context_re.search(text):
        return None, None

    nums = re.findall(r"\d[\d\s]{2,}", text)
    values: list[int] = []
    for n in nums:
        digits = int(re.sub(r"\s+", "", n))
        # Keep realistic salary bounds, ignore phones/ids/noise.
        if 10_000 <= digits <= 2_000_000_000:
            values.append(digits)
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], None
    return min(values), max(values)


def should_skip_enrichment(existing: dict | None, content_hash: str) -> bool:
    if not existing:
        return False
    return (
        existing.get("enriched_at") is not None
        and existing.get("enrichment_version") == ENRICHMENT_VERSION
        and existing.get("enrichment_hash") == content_hash
    )


def get_existing_by_hash(supabase: Client, content_hash: str) -> dict | None:
    res = supabase.table("vacancies").select("*").eq("content_hash", content_hash).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def deterministic_filter(text: str) -> tuple[bool, str, int]:
    score = job_score(text)
    decision = classify_job_or_ad_by_score(text)
    normalized = text.lower()

    if is_ad_or_funnel(text):
        return False, "ad_or_funnel", score

    if decision == "AD":
        return False, "score_ad", score

    if decision == "UNCERTAIN":
        # Keep non-AI filtering strict, but rescue clear internship/job-intent cases.
        uncertain_positive = [
            "стаж",
            "intern",
            "портфолио",
            "резюме",
            "удален",
            "удалён",
        ]
        if any(marker in normalized for marker in uncertain_positive):
            return True, "score_uncertain_but_job_signal", score
        return False, "score_uncertain", score

    return True, "score_job", score


async def run() -> None:
    validate_env()
    supabase = make_supabase()
    source_channels = get_source_channels()

    async with TelegramClient(TELETHON_SESSION_NAME, TG_API_ID, TG_API_HASH) as client:
        if not await client.is_user_authorized():
            if not TG_PHONE:
                raise RuntimeError("First run requires TG_PHONE to complete Telethon login")
            await client.send_code_request(TG_PHONE)
            code = input("Enter Telegram login code: ").strip()
            await client.sign_in(TG_PHONE, code)

        total_processed = 0
        total_filtered_out = 0
        total_enriched = 0

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

            channel_enriched = 0

            for msg in messages:
                raw_text = msg.message.strip()
                if not raw_text:
                    continue

                # 1) scrape + store raw immediately
                content_hash = hashlib.sha256(f"{source_channel}:{msg.id}:{raw_text}".encode("utf-8")).hexdigest()
                source_link = build_source_url(source_channel, msg.id)
                raw_title = extract_raw_title(raw_text)
                salary_min, salary_max = extract_salary_range(raw_text)
                slug = slugify(f"{raw_title or 'job'}-{source_channel.strip('@')}-{msg.id}-{content_hash[:8]}")

                raw_row = {
                    "source_channel": source_channel,
                    "source_message_id": msg.id,
                    "published_at": to_iso(msg.date) or datetime.now(timezone.utc).isoformat(),
                    "raw_text": raw_text,
                    "raw_title": raw_title,
                    "title": raw_title,
                    "description": raw_text,
                    "source_link": source_link,
                    "source_url": source_link,
                    "slug": slug,
                    "content_hash": content_hash,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "pipeline_stage": "raw_saved",
                    "raw_saved_at": datetime.now(timezone.utc).isoformat(),
                }
                supabase.table("vacancies").upsert(raw_row, on_conflict="content_hash", ignore_duplicates=True).execute()

                existing = get_existing_by_hash(supabase, content_hash)
                if should_skip_enrichment(existing, content_hash):
                    continue

                # 2) deterministic filter (NO AI)
                accepted, reason, score = deterministic_filter(raw_text)
                logger.info(
                    "Filter channel=%s message_id=%s score=%s accepted=%s reason=%s",
                    source_channel,
                    msg.id,
                    score,
                    accepted,
                    reason,
                )

                if not accepted:
                    total_filtered_out += 1
                    supabase.table("vacancies").update(
                        {
                            "is_job": False,
                            "filter_status": "rejected",
                            "filter_reason": reason,
                            "pipeline_stage": "filtered_out",
                        }
                    ).eq("content_hash", content_hash).execute()
                    continue

                # 3) AI enrichment only for filtered valid jobs
                ai = await asyncio.to_thread(enrich_vacancy_with_ai, raw_text)
                if ai is None:
                    # no blocking failures
                    supabase.table("vacancies").update(
                        {
                            "is_job": True,
                            "filter_status": "accepted",
                            "filter_reason": reason,
                            "pipeline_stage": "ai_failed",
                        }
                    ).eq("content_hash", content_hash).execute()
                    continue

                # 4) store enriched structured result together with raw row
                enriched_row = {
                    "is_job": True,
                    "filter_status": "accepted",
                    "filter_reason": reason,
                    "pipeline_stage": "enriched",
                    "canonical_title": ai.get("canonical_title"),
                    "display_title": ai.get("display_title"),
                    "seniority": ai.get("seniority"),
                    "employment_type": ai.get("employment_type"),
                    "work_format": ai.get("work_format"),
                    "country": ai.get("country"),
                    "city": ai.get("city"),
                    "system_tags": ai.get("system_tags") or [],
                    "ai_keywords": ai.get("ai_keywords") or [],
                    "industry": ai.get("industry"),
                    "company_type": ai.get("company_type"),
                    "company_name": ai.get("company_name"),
                    "confidence_score": ai.get("confidence_score"),
                    "title": ai.get("display_title") or ai.get("canonical_title") or raw_title,
                    "enriched_at": datetime.now(timezone.utc).isoformat(),
                    "enrichment_version": ENRICHMENT_VERSION,
                    "enrichment_hash": content_hash,
                }
                supabase.table("vacancies").update(enriched_row).eq("content_hash", content_hash).execute()

                channel_enriched += 1
                total_enriched += 1

            total_processed += len(messages)
            logger.info(
                "Channel summary %s: processed=%s filtered_out=%s enriched=%s",
                source_channel,
                len(messages),
                total_filtered_out,
                channel_enriched,
            )

        logger.info(
            "Total summary: channels=%s processed=%s filtered_out=%s enriched=%s",
            len(source_channels),
            total_processed,
            total_filtered_out,
            total_enriched,
        )


if __name__ == "__main__":
    asyncio.run(run())
