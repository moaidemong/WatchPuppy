from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

logger = logging.getLogger("watchpuppy.backbone")
_ALERT_EXECUTOR: ThreadPoolExecutor | None = None


def _telegram_chat_ids() -> list[str]:
    raw_chat_ids = os.getenv("WATCHPUPPY_TELEGRAM_CHAT_IDS", "").strip()
    if raw_chat_ids:
        return [item.strip() for item in raw_chat_ids.split(",") if item.strip()]

    legacy_chat_id = os.getenv("WATCHPUPPY_TELEGRAM_CHAT_ID", "").strip()
    return [legacy_chat_id] if legacy_chat_id else []


def _telegram_send_photo_enabled() -> bool:
    return os.getenv("WATCHPUPPY_TELEGRAM_SEND_PHOTO", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _get_alert_executor() -> ThreadPoolExecutor:
    global _ALERT_EXECUTOR
    if _ALERT_EXECUTOR is None:
        max_workers = int(os.getenv("WATCHPUPPY_TELEGRAM_MAX_ALERT_WORKERS", "2").strip() or "2")
        _ALERT_EXECUTOR = ThreadPoolExecutor(max_workers=max(1, max_workers), thread_name_prefix="wp-telegram")
    return _ALERT_EXECUTOR


def _send_failed_get_up_alert_sync(
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
    chat_ids = _telegram_chat_ids()
    if not token or not chat_ids:
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

    results: list[dict[str, Any]] = []
    try:
        send_photo = _telegram_send_photo_enabled()

        def _send_one(chat_id: str) -> dict[str, Any]:
            if send_photo and snapshot_path.exists():
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
                "chat_id": chat_id,
                "ok": bool(payload.get("ok", False)),
                "result_message_id": ((payload.get("result") or {}).get("message_id")),
            }

        max_workers = min(4, max(1, len(chat_ids)))
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="wp-telegram-recipient") as pool:
            futures = {pool.submit(_send_one, chat_id): chat_id for chat_id in chat_ids}
            for future in as_completed(futures):
                results.append(future.result())
        return {
            "channel": "telegram",
            "status": "sent",
            "mode": "photo" if send_photo and snapshot_path.exists() else "text",
            "recipient_count": len(results),
            "results": results,
        }
    except Exception as exc:
        return {
            "channel": "telegram",
            "status": "failed",
            "error": str(exc),
        }


def send_failed_get_up_alert_async(
    *,
    event_id: str,
    camera_id: str,
    epoch: str,
    score: float,
    threshold: float,
    snapshot_path: Path,
    transaction_id: str | None = None,
) -> dict[str, Any]:
    enabled = os.getenv("WATCHPUPPY_TELEGRAM_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return {"channel": "telegram", "status": "disabled"}

    token = os.getenv("WATCHPUPPY_TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids = _telegram_chat_ids()
    if not token or not chat_ids:
        return {"channel": "telegram", "status": "missing_credentials"}

    executor = _get_alert_executor()

    def _job() -> None:
        result = _send_failed_get_up_alert_sync(
            event_id=event_id,
            camera_id=camera_id,
            epoch=epoch,
            score=score,
            threshold=threshold,
            snapshot_path=snapshot_path,
        )
        logger.info(
            json.dumps(
                {
                    "camera_id": camera_id,
                    "event_id": event_id,
                    "transaction_id": transaction_id,
                    "notification_async_result": result,
                },
                ensure_ascii=False,
            )
        )

    executor.submit(_job)
    return {
        "channel": "telegram",
        "status": "queued",
        "mode": "photo" if _telegram_send_photo_enabled() and snapshot_path.exists() else "text",
        "recipient_count": len(chat_ids),
    }
