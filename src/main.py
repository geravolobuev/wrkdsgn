import asyncio
import hashlib
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

from parser.deterministic_prefilter import run_prefilter
from src.enrichment.openrouter_client import EnrichmentResult, enrich_with_openrouter

load_dotenv()

TG_API_ID = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_PHONE = os.getenv("TG_PHONE", "")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "")
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
TELETHON_SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "telegram_session")
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "30"))
ENRICHMENT_VERSION = os.getenv("ENRICHMENT_VERSION", "v1")


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


def infer_remote_type(text: str) -> str | None:
    low = text.lower()
    if any(token in low for token in ["remote", "удален", "удалён"]):
        return "remote"
    if any(token in low for token in ["hybrid", "гибрид"]):
        return "hybrid"
    if any(token in low for token in ["onsite", "офис"]):
        return "onsite"
    return None


def infer_tags(text: str) -> list[str]:
    low = text.lower()
    tags: list[str] = []
    dictionary = {
        "ux": ["ux"],
        "ui": ["ui"],
        "product_design": ["product designer", "продукт"],
        "graphic_design": ["graphic", "графическ"],
        "motion": ["motion"],
        "branding": ["brand", "branding", "бренд"],
        "web_design": ["web", "веб"],
        "freelance": ["freelance", "фриланс"],
    }
    for tag, needles in dictionary.items():
        if any(n in low for n in needles):
            tags.append(tag)
    return tags


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
        if company is None and ("компан" in low or "company" in low):
            company = line
        if salary is None and ("зарп" in low or "$" in line or "₽" in line or "usd" in low or "eur" in low):
            salary = line
        if location is None and (
            "удален" in low
            or "удалён" in low
            or "remote" in low
            or "офис" in low
            or "location" in low
            or "city" in low
        ):
            location = line

    description = text.strip()

    return {
        "title": title,
        "company": company,
        "salary": salary,
        "location": location,
        "description": description,
        "level": infer_seniority(description),
        "remote_type": infer_remote_type(description),
        "specializations": infer_tags(description),
        "employment_type": infer_employment_type(description),
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


def get_existing_by_source(supabase: Client, source_channel: str, message_id: int) -> dict | None:
    res = (
        supabase.table("vacancies")
        .select("*")
        .eq("source_channel", source_channel)
        .eq("source_message_id", message_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


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


def merge_metadata(base: dict, ai: EnrichmentResult | None) -> dict:
    salary_min, salary_max = parse_salary_range(base.get("salary"))

    merged = {
        "country": None,
        "city": None,
        "remote_type": base.get("remote_type"),
        "employment_type": base.get("employment_type"),
        "level": base.get("level"),
        "role_type": None,
        "specializations": base.get("specializations") or [],
        "semantic_tags": [],
        "tools": [],
        "language": [],
        "salary_min": salary_min,
        "salary_max": salary_max,
        "is_job": True,
    }

    if ai is None:
        return merged

    merged["is_job"] = ai.is_job
    merged["country"] = ai.country
    merged["city"] = ai.city
    merged["remote_type"] = ai.remote_type or merged["remote_type"]
    merged["employment_type"] = ai.employment_type or merged["employment_type"]
    merged["level"] = ai.level or merged["level"]
    merged["role_type"] = ai.role_type
    merged["specializations"] = ai.specializations or merged["specializations"]
    merged["semantic_tags"] = ai.semantic_tags
    merged["tools"] = ai.tools
    merged["language"] = ai.language
    merged["salary_min"] = ai.salary_min if ai.salary_min is not None else merged["salary_min"]
    merged["salary_max"] = ai.salary_max if ai.salary_max is not None else merged["salary_max"]
    return merged


def is_duplicate_content_hash_error(exc: Exception) -> bool:
    if not isinstance(exc, APIError):
        return False
    payload = getattr(exc, "args", [None])[0]
    if not isinstance(payload, dict):
        return False
    # Be tolerant to payload format differences across postgrest client versions.
    if payload.get("code") != "23505":
        return False
    return payload.get("code") == "23505"


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
        total_prefilter_rejected = 0
        total_ai_rejected = 0
        total_saved = 0

        for source_channel in source_channels:
            try:
                source_entity = await client.get_entity(source_channel)
            except Exception as exc:
                print(f"Skip channel {source_channel}: cannot resolve ({exc})")
                continue

            messages = []
            async for message in client.iter_messages(source_entity, limit=FETCH_LIMIT):
                if message.message:
                    messages.append(message)
            messages.reverse()

            channel_saved = 0

            for msg in messages:
                raw_text = msg.message.strip()
                content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

                pre = run_prefilter(raw_text)
                print(
                    f"Prefilter channel={source_channel} message_id={msg.id} score={pre['score']} "
                    f"accepted={pre['accepted']} positive={pre['matched_positive']} negative={pre['matched_negative']}"
                )

                if not pre["accepted"]:
                    total_prefilter_rejected += 1
                    continue

                existing = get_existing_by_source(supabase, source_channel, msg.id)
                if should_skip_enrichment(existing, content_hash):
                    continue

                duplicate = get_existing_by_hash(supabase, content_hash)
                if duplicate and not existing:
                    if should_skip_enrichment(duplicate, content_hash):
                        continue

                base = extract_fields(raw_text)
                ai = enrich_with_openrouter(raw_text)
                metadata = merge_metadata(base, ai)

                if not metadata["is_job"]:
                    total_ai_rejected += 1
                    continue

                source_link = build_source_url(source_channel, msg.id)
                slug = slugify(f"{base['title'] or 'job'}-{source_channel.strip('@')}-{msg.id}")

                row = {
                    "source_channel": source_channel,
                    "source_message_id": msg.id,
                    "published_at": to_iso(msg.date) or datetime.now(timezone.utc).isoformat(),
                    "raw_text": raw_text,
                    "title": base["title"],
                    "company": base["company"],
                    "location": base["location"],
                    "description": base["description"],
                    "source_link": source_link,
                    "source_url": source_link,
                    "slug": slug,
                    "content_hash": content_hash,
                    "is_job": metadata["is_job"],
                    "country": metadata["country"],
                    "city": metadata["city"],
                    "remote_type": metadata["remote_type"],
                    "employment_type": metadata["employment_type"],
                    "level": metadata["level"],
                    "role_type": metadata["role_type"],
                    "specializations": metadata["specializations"],
                    "semantic_tags": metadata["semantic_tags"],
                    "tools": metadata["tools"],
                    "language": metadata["language"],
                    "salary_min": metadata["salary_min"],
                    "salary_max": metadata["salary_max"],
                    "enriched_at": datetime.now(timezone.utc).isoformat(),
                    "enrichment_version": ENRICHMENT_VERSION,
                    "enrichment_hash": content_hash,
                }

                if existing:
                    supabase.table("vacancies").update(row).eq("id", existing["id"]).execute()
                else:
                    # Conflict-safe insert: ignore duplicate content_hash at DB level.
                    supabase.table("vacancies").upsert(
                        row,
                        on_conflict="content_hash",
                        ignore_duplicates=True,
                    ).execute()

                channel_saved += 1
                total_saved += 1

            total_processed += len(messages)
            print(
                f"Channel summary {source_channel}: processed={len(messages)} saved={channel_saved}"
            )

        print(
            f"Total summary: channels={len(source_channels)} processed={total_processed} "
            f"prefilter_rejected={total_prefilter_rejected} ai_rejected={total_ai_rejected} saved={total_saved}"
        )


if __name__ == "__main__":
    asyncio.run(run())
