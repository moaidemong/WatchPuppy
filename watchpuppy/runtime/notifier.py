from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests


def send_failed_get_up_alert(
    *,
    event_id: str,
    camera_id: str,
    epoch: str,
    score: float,
    threshold: float,
    snapshot_path: Path,
) -> dict[str, Any]:
    enabled = os.getenv("WATCHPUPPY_TELEGRAM_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return {"channel": "telegram", "status": "disabled"}

    token = os.getenv("WATCHPUPPY_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("WATCHPUPPY_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return {"channel": "telegram", "status": "missing_credentials"}

    base_url = f"https://api.telegram.org/bot{token}"
    caption = (
        "WatchPuppy Alert\n"
        f"event={event_id}\n"
        f"camera={camera_id}\n"
        f"epoch={epoch}\n"
        f"label=failed_get_up_attempt\n"
        f"score={score:.3f}\n"
        f"threshold={threshold:.3f}"
    )

    try:
        if snapshot_path.exists():
            with snapshot_path.open("rb") as fp:
                response = requests.post(
                    f"{base_url}/sendPhoto",
                    data={"chat_id": chat_id, "caption": caption},
                    files={"photo": fp},
                    timeout=10,
                )
        else:
            response = requests.post(
                f"{base_url}/sendMessage",
                data={"chat_id": chat_id, "text": caption},
                timeout=10,
            )
        response.raise_for_status()
        payload = response.json()
        return {
            "channel": "telegram",
            "status": "sent",
            "ok": bool(payload.get("ok", False)),
            "result_message_id": ((payload.get("result") or {}).get("message_id")),
        }
    except Exception as exc:
        return {
            "channel": "telegram",
            "status": "failed",
            "error": str(exc),
        }
