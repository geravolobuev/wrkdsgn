#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import getpass
import os
from pathlib import Path

from telethon import TelegramClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a CI-only Telethon session and print its base64 form for GitHub Secrets.",
    )
    parser.add_argument("--api-id", type=int, default=int(os.getenv("TG_API_ID", "0") or "0"))
    parser.add_argument("--api-hash", default=os.getenv("TG_API_HASH", ""))
    parser.add_argument("--phone", default=os.getenv("TG_PHONE", ""))
    parser.add_argument("--session-name", default="telegram_session_ci")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where the .session file will be written.",
    )
    return parser


async def create_session(api_id: int, api_hash: str, phone: str, session_path: Path) -> None:
    client = TelegramClient(str(session_path), api_id, api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            await client.send_code_request(phone)
            code = input("Enter Telegram login code: ").strip()
            try:
                await client.sign_in(phone=phone, code=code)
            except Exception:
                password = getpass.getpass("Enter Telegram 2FA password: ")
                await client.sign_in(password=password)
    finally:
        await client.disconnect()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.api_id or not args.api_hash or not args.phone:
        parser.error("api-id, api-hash, and phone are required (flags or env TG_API_ID/TG_API_HASH/TG_PHONE)")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    session_path = output_dir / args.session_name

    import asyncio

    asyncio.run(create_session(args.api_id, args.api_hash, args.phone, session_path))

    session_file = session_path.with_suffix(".session")
    if not session_file.exists():
        raise FileNotFoundError(f"Session file not found: {session_file}")

    encoded = base64.b64encode(session_file.read_bytes()).decode("utf-8")

    print("\nSession created:")
    print(session_file)
    print("\nGitHub Secret name:")
    print("TELETHON_SESSION_B64")
    print("\nGitHub Secret value:")
    print(encoded)
    print("\nIMPORTANT:")
    print("- Use this session ONLY in GitHub Actions.")
    print("- Do not reuse this same session locally, or Telegram may invalidate it again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
