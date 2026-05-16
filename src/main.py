import asyncio
import hashlib
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from supabase import Client, create_client
from telethon import TelegramClient

load_dotenv()

TG_API_ID = int(os.getenv("TG_API_ID", "0"))
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_PHONE = os.getenv("TG_PHONE", "")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_TARGET_CHAT_ID = os.getenv("TG_TARGET_CHAT_ID", "")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "")
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
        "SOURCE_CHANNEL": SOURCE_CHANNEL,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SERVICE_ROLE_KEY": SUPABASE_SERVICE_ROLE_KEY,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def make_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def normalize_channel(value: str) -> str:
    channel = value.strip()
    if channel.startswith("https://t.me/"):
        channel = "@" + channel.split("https://t.me/", 1)[1].strip("/")
    return channel


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
        if salary is None and ("зарп" in low or "$" in line or "₽" in line or "usd" in low):
            salary = line
        if location is None and ("удален" in low or "remote" in low or "офис" in low or "location" in low):
            location = line
        if contact is None and ("@" in line or "tg:" in low or "контакт" in low):
            contact = line

    return {
        "title": title,
        "company": company,
        "salary": salary,
        "location": location,
        "stack": None,
        "contact": contact,
    }


def build_source_url(channel: str, message_id: int) -> str | None:
    if channel.startswith("@"):
        return f"https://t.me/{channel[1:]}/{message_id}"
    return None


def to_iso(ts) -> str | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()


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


def exists_in_db(supabase: Client, source_channel: str, message_id: int) -> bool:
    res = (
        supabase.table("vacancies")
        .select("id")
        .eq("source_channel", source_channel)
        .eq("source_message_id", message_id)
        .limit(1)
        .execute()
    )
    return bool(res.data)


async def run() -> None:
    validate_env()
    supabase = make_supabase()
    source_channel = normalize_channel(SOURCE_CHANNEL)

    async with TelegramClient(TELETHON_SESSION_NAME, TG_API_ID, TG_API_HASH) as client:
        if not await client.is_user_authorized():
            if not TG_PHONE:
                raise RuntimeError("First run requires TG_PHONE to complete Telethon login")
            await client.send_code_request(TG_PHONE)
            code = input("Enter Telegram login code: ").strip()
            await client.sign_in(TG_PHONE, code)

        try:
            source_entity = await client.get_entity(source_channel)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to resolve SOURCE_CHANNEL '{source_channel}'. "
                "Use public channel username like @channel_name or https://t.me/channel_name"
            ) from exc

        messages = []
        async for message in client.iter_messages(source_entity, limit=FETCH_LIMIT):
            if message.message:
                messages.append(message)

        messages.reverse()
        new_count = 0

        for msg in messages:
            if exists_in_db(supabase, source_channel, msg.id):
                continue

            raw_text = msg.message.strip()
            content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            fields = extract_fields(raw_text)

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
                "source_url": build_source_url(source_channel, msg.id),
                "content_hash": content_hash,
            }

            supabase.table("vacancies").insert(row).execute()

            post_text = (
                "Новая вакансия\n\n"
                f"{raw_text}\n\n"
                f"Источник: {row['source_url'] or source_channel}"
            )
            ok, err = repost_to_bot(post_text)
            if ok:
                new_count += 1
            else:
                print(f"Repost failed for message {msg.id}: {err}")

        print(f"Processed: {len(messages)}, new: {new_count}")


if __name__ == "__main__":
    asyncio.run(run())
