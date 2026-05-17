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

from parser.ad_classifier import is_ad_or_funnel
from parser.job_classifier import classify_job_or_ad_by_score, job_score
from parser.job_splitter import split_jobs
from parser.location_extractor import extract_location
from parser.openrouter_client import classify_uncertain_job_ad, enrich_vacancy_with_ai
from parser.role_extractor import extract_canonical_role
from parser.taxonomy_mapper import map_role_to_taxonomy

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
ENRICHMENT_VERSION = os.getenv("ENRICHMENT_VERSION", "v2_strict")


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


def infer_seniority(text: str) -> str | None:
    low = text.lower()
    if "junior" in low or "джун" in low:
        return "junior"
    if "middle" in low or "мид" in low:
        return "middle"
    if "senior" in low or "сеньор" in low:
        return "senior"
    if "lead" in low or "тимлид" in low:
        return "lead"
    if "intern" in low or "стаж" in low:
        return "intern"
    return None


def infer_employment_type(text: str) -> str | None:
    low = text.lower()
    if any(x in low for x in ["full-time", "full time", "полная занятость"]):
        return "full_time"
    if any(x in low for x in ["part-time", "part time", "частичная занятость"]):
        return "part_time"
    if any(x in low for x in ["contract", "контракт"]):
        return "contract"
    if any(x in low for x in ["freelance", "фриланс"]):
        return "freelance"
    if any(x in low for x in ["intern", "стаж"]):
        return "internship"
    return None


def extract_fields(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else None

    company = None
    salary = None
    location = None

    for line in lines:
        low = line.lower()
        if company is None and ("компан" in low or "company" in low or " в " in low):
            company = line[:120]
        if salary is None and ("зарп" in low or "$" in line or "₽" in line or "usd" in low or "eur" in low):
            salary = line
        if location is None and (
            "удален" in low
            or "удалён" in low
            or "remote" in low
            or "офис" in low
            or "location" in low
            or "city" in low
            or "hybrid" in low
        ):
            location = line

    return {
        "raw_title": title,
        "company": company,
        "salary": salary,
        "location": location,
        "description": text.strip(),
        "level": infer_seniority(text),
        "employment_type": infer_employment_type(text),
    }


def parse_salary_range(salary_line: str | None) -> tuple[int | None, int | None]:
    if not salary_line:
        return None, None
    nums = re.findall(r"\d[\d\s]{2,}", salary_line)
    values: list[int] = []
    for n in nums:
        digits = int(re.sub(r"\s+", "", n))
        if digits > 0:
            values.append(digits)
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], None
    return min(values), max(values)


def build_source_url(channel: str, message_id: int) -> str | None:
    if channel.startswith("@"):
        return f"https://t.me/{channel[1:]}/{message_id}"
    return None


def get_existing_by_hash(supabase: Client, content_hash: str) -> dict | None:
    res = supabase.table("vacancies").select("*").eq("content_hash", content_hash).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def should_skip_enrichment(existing: dict | None, content_hash: str) -> bool:
    if not existing:
        return False
    return (
        existing.get("enriched_at") is not None
        and existing.get("enrichment_version") == ENRICHMENT_VERSION
        and existing.get("enrichment_hash") == content_hash
    )


def _final_stage_decision(text: str) -> tuple[bool, str, int]:
    score = job_score(text)
    scored = classify_job_or_ad_by_score(text)

    if scored == "JOB":
        return True, "score_job", score
    if scored == "AD":
        return False, "score_ad", score

    ai_decision = classify_uncertain_job_ad(text)
    if ai_decision == "JOB":
        return True, "ai_job", score
    if ai_decision == "AD":
        return False, "ai_ad", score

    # deterministic fallback when AI uncertain/unavailable
    return score >= 1, "fallback_score", score


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

            for msg in messages:
                raw_text = msg.message.strip()

                is_job, decision_source, score = _final_stage_decision(raw_text)
                logger.info(
                    "Classify channel=%s message_id=%s score=%s decision=%s source=%s",
                    source_channel,
                    msg.id,
                    score,
                    "JOB" if is_job else "AD",
                    decision_source,
                )

                if not is_job or is_ad_or_funnel(raw_text):
                    total_rejected += 1
                    continue

                split_items = split_jobs(raw_text)

                for part_idx, item in enumerate(split_items):
                    job_text = (item.get("raw_text") or "").strip()
                    if not job_text:
                        continue

                    content_hash = hashlib.sha256(
                        f"{source_channel}:{msg.id}:{part_idx}:{job_text}".encode("utf-8")
                    ).hexdigest()

                    existing = get_existing_by_hash(supabase, content_hash)
                    if should_skip_enrichment(existing, content_hash):
                        continue

                    base = extract_fields(job_text)
                    canonical_title = extract_canonical_role(job_text)
                    specializations = map_role_to_taxonomy(canonical_title)

                    # Strict taxonomy gate: keep only jobs mapped to controlled vocabulary
                    if not specializations:
                        total_rejected += 1
                        continue

                    loc = extract_location(job_text)
                    ai = enrich_vacancy_with_ai(job_text)

                    if ai is not None and ai.get("is_job") is False:
                        total_rejected += 1
                        continue

                    salary_min, salary_max = parse_salary_range(base.get("salary"))
                    if ai is not None:
                        salary_min = ai.get("salary_min") if ai.get("salary_min") is not None else salary_min
                        salary_max = ai.get("salary_max") if ai.get("salary_max") is not None else salary_max

                    source_link = build_source_url(source_channel, msg.id)
                    slug = slugify(f"{canonical_title}-{source_channel.strip('@')}-{msg.id}-{part_idx}")

                    row = {
                        "source_channel": source_channel,
                        "source_message_id": msg.id,
                        "published_at": to_iso(msg.date) or datetime.now(timezone.utc).isoformat(),
                        "raw_text": job_text,
                        "raw_title": base["raw_title"],
                        "canonical_title": canonical_title,
                        "title": canonical_title,
                        "company": base["company"],
                        "location": base["location"],
                        "description": base["description"],
                        "source_link": source_link,
                        "source_url": source_link,
                        "slug": slug,
                        "content_hash": content_hash,
                        "is_job": True,
                        "country": loc["country"] or (ai.get("country") if ai else None),
                        "city": loc["city"] or (ai.get("city") if ai else None),
                        "remote_type": loc["remote_type"] or (ai.get("remote_type") if ai else None),
                        "employment_type": (ai.get("employment_type") if ai else None) or base["employment_type"],
                        "level": (ai.get("level") if ai else None) or base["level"],
                        "role_type": ai.get("role_type") if ai else None,
                        "specializations": specializations,
                        "semantic_tags": ai.get("semantic_tags") if ai else [],
                        "tools": ai.get("tools") if ai else [],
                        "language": ai.get("language") if ai else [],
                        "salary_min": salary_min,
                        "salary_max": salary_max,
                        "enriched_at": datetime.now(timezone.utc).isoformat(),
                        "enrichment_version": ENRICHMENT_VERSION,
                        "enrichment_hash": content_hash,
                    }

                    supabase.table("vacancies").upsert(
                        row,
                        on_conflict="content_hash",
                        ignore_duplicates=True,
                    ).execute()

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
