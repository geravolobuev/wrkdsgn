import asyncio
import hashlib
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import Client, create_client
from telethon import TelegramClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from parser.job_classifier import classify_job_post_with_details

load_dotenv()

TG_API_ID = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_PHONE = os.getenv("TG_PHONE", "")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_TARGET_CHAT_ID = os.getenv("TG_TARGET_CHAT_ID", "")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "")
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
TELETHON_SESSION_NAME = os.getenv("TELETHON_SESSION_NAME", "telegram_session")
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "30"))


def validate_env() -> None:
    required = {
        "TG_API_ID": TG_API_ID,
        "TG_API_HASH": TG_API_HASH,
        "TG_BOT_TOKEN": TG_BOT_TOKEN,
        "TG_TARGET_CHAT_ID": TG_TARGET_CHAT_ID,
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


def infer_remote(text: str) -> bool:
    low = text.lower()
    return any(token in low for token in ["remote", "удален", "удалён", "гибрид", "hybrid"])


def infer_tags(text: str) -> list[str]:
    low = text.lower()
    tags: list[str] = []
    dictionary = {
        "ux": ["ux"],
        "ui": ["ui"],
        "product": ["product designer", "product"],
        "graphic": ["graphic", "графическ"],
        "motion": ["motion"],
        "brand": ["brand", "branding"],
        "web": ["web", "веб"],
        "mobile": ["mobile", "ios", "android"],
        "figma": ["figma"],
        "freelance": ["freelance", "фриланс"],
    }
    for tag, needles in dictionary.items():
        if any(n in low for n in needles):
            tags.append(tag)
    return tags


def extract_fields(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else None

    company = None
    salary = None
    location = None
    contact = None

    for line in lines:
        low = line.lower()
        if company is None and ("компан" in low or "company" in low):
            company = line
        if salary is None and (
            "зарп" in low or "$" in line or "₽" in line or "usd" in low or "eur" in low
        ):
            salary = line
        if location is None and (
            "удален" in low or "удалён" in low or "remote" in low or "офис" in low or "location" in low
        ):
            location = line
        if contact is None and ("@" in line or "tg:" in low or "контакт" in low):
            contact = line

    description = text.strip()
    seniority = infer_seniority(description)
    remote = infer_remote(description)
    tags = infer_tags(description)

    return {
        "title": title,
        "company": company,
        "salary": salary,
        "location": location,
        "stack": None,
        "contact": contact,
        "description": description,
        "seniority": seniority,
        "remote": remote,
        "tags": tags,
    }


def build_source_url(channel: str, message_id: int) -> str | None:
    if channel.startswith("@"):
        return f"https://t.me/{channel[1:]}/{message_id}"
    return None


def repost_to_bot(text: str) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_TARGET_CHAT_ID,
        "text": text[:4000],
        "disable_web_page_preview": True,
    }
    response = requests.post(url, json=payload, timeout=20)
    if response.status_code >= 400:
        return False, response.text
    return True, ""


def get_existing_vacancy(supabase: Client, source_channel: str, message_id: int) -> dict | None:
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


def mark_reposted(supabase: Client, vacancy_id: int) -> None:
    supabase.table("vacancies").update({"reposted_at": datetime.now(timezone.utc).isoformat()}).eq("id", vacancy_id).execute()


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
        total_accepted = 0
        total_rejected = 0
        total_reposted = 0

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
            channel_reposted = 0
            channel_accepted = 0
            channel_rejected = 0

            for msg in messages:
                raw_text = msg.message.strip()
                cls = classify_job_post_with_details(raw_text)
                decision = "ACCEPT" if cls["accepted"] else "REJECT"
                print(
                    f"Classifier channel={source_channel} message_id={msg.id} score={cls['score']} "
                    f"confidence={cls['confidence']} decision={decision} "
                    f"positives={cls['matched_positive']} negatives={cls['matched_negative']}"
                )

                if not cls["accepted"]:
                    channel_rejected += 1
                    continue

                channel_accepted += 1
                content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

                existing = get_existing_vacancy(supabase, source_channel, msg.id)
                vacancy_id = None

                if existing:
                    vacancy_id = existing.get("id")
                    if existing.get("reposted_at") is not None:
                        continue
                    raw_text = existing.get("raw_text") or raw_text
                    source_url = existing.get("source_link") or existing.get("source_url") or build_source_url(source_channel, msg.id)
                else:
                    duplicate_by_hash = get_existing_by_hash(supabase, content_hash)
                    if duplicate_by_hash:
                        dup_id = duplicate_by_hash.get("id")
                        if duplicate_by_hash.get("reposted_at") is not None:
                            print(
                                f"Skip duplicate content_hash for channel={source_channel} "
                                f"message_id={msg.id} existing_id={dup_id}"
                            )
                            continue

                        vacancy_id = dup_id
                        raw_text = duplicate_by_hash.get("raw_text") or raw_text
                        source_url = (
                            duplicate_by_hash.get("source_link")
                            or duplicate_by_hash.get("source_url")
                            or build_source_url(source_channel, msg.id)
                        )
                    else:
                        fields = extract_fields(raw_text)
                        source_link = build_source_url(source_channel, msg.id)
                        slug = slugify(f"{fields['title'] or 'job'}-{source_channel.strip('@')}-{msg.id}")

                        row = {
                            "source_channel": source_channel,
                            "source_message_id": msg.id,
                            "published_at": to_iso(msg.date) or datetime.now(timezone.utc).isoformat(),
                            "raw_text": raw_text,
                            "title": fields["title"],
                            "company": fields["company"],
                            "salary": fields["salary"],
                            "location": fields["location"],
                            "stack": fields["stack"],
                            "contact": fields["contact"],
                            "description": fields["description"],
                            "remote": fields["remote"],
                            "seniority": fields["seniority"],
                            "tags": fields["tags"],
                            "source_link": source_link,
                            "source_url": source_link,
                            "slug": slug,
                            "content_hash": content_hash,
                            "reposted_at": None,
                        }

                        insert_res = supabase.table("vacancies").insert(row).execute()
                        inserted = insert_res.data or []
                        if inserted:
                            vacancy_id = inserted[0].get("id")
                        source_url = source_link

                post_text = (
                    "Новая вакансия\n\n"
                    f"{raw_text}\n\n"
                    f"Источник: {source_url or source_channel}"
                )
                ok, err = repost_to_bot(post_text)
                if ok:
                    channel_reposted += 1
                    if vacancy_id is not None:
                        try:
                            mark_reposted(supabase, vacancy_id)
                        except Exception as exc:
                            print(f"Warning: cannot update reposted_at for vacancy {vacancy_id}: {exc}")
                else:
                    print(f"Repost failed for channel={source_channel} message_id={msg.id}: {err}")

            total_processed += len(messages)
            total_accepted += channel_accepted
            total_rejected += channel_rejected
            total_reposted += channel_reposted

            print(
                f"Channel summary {source_channel}: processed={len(messages)} accepted={channel_accepted} "
                f"rejected={channel_rejected} reposted={channel_reposted}"
            )

        print(
            f"Total summary: channels={len(source_channels)} processed={total_processed} "
            f"accepted={total_accepted} rejected={total_rejected} reposted={total_reposted}"
        )


if __name__ == "__main__":
    asyncio.run(run())
