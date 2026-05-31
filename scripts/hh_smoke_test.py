#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.hh.ru"
DEFAULT_USER_AGENT = "wrkdsgn/1.0 (hello@wrkdsgn.vercel.app)"
DEFAULT_QUERIES = [
    "designer",
    "art director",
    "graphic designer",
    "графический дизайнер",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone smoke test for public HH API access.",
    )
    parser.add_argument(
        "--user-agent",
        default=os.getenv("HH_USER_AGENT", DEFAULT_USER_AGENT),
        help="Value for HH-User-Agent header.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("HH_TIMEOUT", "20")),
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=1,
        help="Vacancy page size for smoke requests.",
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Repeatable vacancy search query. Defaults to a small mixed RU/EN set.",
    )
    parser.add_argument(
        "--host",
        default="hh.ru",
        help="HH host parameter.",
    )
    parser.add_argument(
        "--locale",
        default="RU",
        help="HH locale parameter.",
    )
    return parser


def request_json(
    *,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None,
    timeout: int,
) -> tuple[int, dict[str, str], str, Any | None]:
    full_url = url
    if params:
        full_url = f"{url}?{urlencode(params, doseq=True)}"

    request = Request(full_url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            body_bytes = response.read()
            status = response.getcode()
            response_headers = dict(response.headers.items())
    except HTTPError as exc:
        body_bytes = exc.read()
        status = exc.code
        response_headers = dict(exc.headers.items())
    except URLError as exc:
        raise RuntimeError(f"url_error:{exc}") from exc

    body_text = body_bytes.decode("utf-8", errors="replace")[:1200]
    parsed: Any | None = None
    try:
        parsed = json.loads(body_text)
    except ValueError:
        parsed = None
    return status, response_headers, body_text, parsed


def print_result(label: str, status: int, body_text: str, parsed: Any | None) -> None:
    print(f"\n=== {label} ===")
    print(f"status: {status}")
    if isinstance(parsed, dict):
        print("json_keys:", sorted(parsed.keys())[:20])
        if "errors" in parsed:
            print("errors:", json.dumps(parsed["errors"], ensure_ascii=False))
        if "request_id" in parsed:
            print("request_id:", parsed["request_id"])
        if "found" in parsed:
            print("found:", parsed["found"])
        if "pages" in parsed:
            print("pages:", parsed["pages"])
        if "items" in parsed and isinstance(parsed["items"], list):
            print("items:", len(parsed["items"]))
    else:
        print("body_preview:", body_text.replace("\n", " ")[:600])


def main() -> int:
    args = build_parser().parse_args()
    headers = {
        "HH-User-Agent": args.user_agent,
        "User-Agent": args.user_agent,
        "Accept": "application/json",
    }
    queries = args.queries or list(DEFAULT_QUERIES)

    print("HH smoke test starting")
    print("base_url:", BASE_URL)
    print("user_agent:", args.user_agent)
    print("timeout:", args.timeout)
    print("queries:", queries)

    checks_failed = 0
    vacancy_access_ok = False

    try:
        status, _, body_text, parsed = request_json(
            url=f"{BASE_URL}/areas",
            headers=headers,
            params=None,
            timeout=args.timeout,
        )
        print_result("GET /areas", status, body_text, parsed)
        if status >= 400:
            checks_failed += 1
    except RuntimeError as exc:
        print("\n=== GET /areas ===")
        print("request_exception:", repr(exc))
        checks_failed += 1

    for query in queries:
        try:
            status, _, body_text, parsed = request_json(
                url=f"{BASE_URL}/vacancies",
                headers=headers,
                params={
                    "text": query,
                    "page": 0,
                    "per_page": args.per_page,
                    "host": args.host,
                    "locale": args.locale,
                    "search_field": "name",
                },
                timeout=args.timeout,
            )
            print_result(f"GET /vacancies text={query!r}", status, body_text, parsed)
            if status < 400:
                vacancy_access_ok = True
            else:
                checks_failed += 1
        except RuntimeError as exc:
            print(f"\n=== GET /vacancies text={query!r} ===")
            print("request_exception:", repr(exc))
            checks_failed += 1

    if vacancy_access_ok:
        print("\nRESULT: HH vacancy search is reachable from this machine/IP.")
        return 0

    print("\nRESULT: HH vacancy search is NOT reachable from this machine/IP.")
    return 1 if checks_failed else 0


if __name__ == "__main__":
    sys.exit(main())
