#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


DEFAULT_ENV_PATH = Path("/home/moai/Workspace/Codex/WatchPuppy/configs/watchpuppy.env")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Telegram bot updates and print readable chat/user ids."
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_PATH),
        help="Path to watchpuppy env file containing WATCHPUPPY_TELEGRAM_BOT_TOKEN",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw Telegram JSON instead of a compact summary",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of updates to fetch",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def telegram_updates(token: str, *, limit: int) -> dict[str, Any]:
    query = urlencode({"limit": max(1, limit), "timeout": 1})
    url = f"https://api.telegram.org/bot{token}/getUpdates?{query}"
    with urlopen(url, timeout=10) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def summarize_updates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload.get("result", []):
        message = item.get("message") or item.get("edited_message") or {}
        if not message:
            continue
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        rows.append(
            {
                "update_id": item.get("update_id"),
                "chat_id": chat.get("id"),
                "chat_type": chat.get("type"),
                "chat_username": chat.get("username"),
                "sender_id": sender.get("id"),
                "sender_is_bot": sender.get("is_bot"),
                "sender_username": sender.get("username"),
                "sender_name": " ".join(
                    part for part in [sender.get("first_name"), sender.get("last_name")] if part
                )
                or None,
                "text": message.get("text"),
                "date": message.get("date"),
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    env_values = load_env_file(Path(args.env_file))
    token = os.getenv("WATCHPUPPY_TELEGRAM_BOT_TOKEN") or env_values.get("WATCHPUPPY_TELEGRAM_BOT_TOKEN", "")
    token = token.strip()
    if not token:
        print("WATCHPUPPY_TELEGRAM_BOT_TOKEN not found", flush=True)
        return 1

    try:
        payload = telegram_updates(token, limit=args.limit)
    except HTTPError as exc:
        print(f"HTTP error: {exc.code} {exc.reason}", flush=True)
        return 2
    except URLError as exc:
        print(f"Network error: {exc.reason}", flush=True)
        return 3

    if args.raw:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    rows = summarize_updates(payload)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
