#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import fcntl
import json
import logging
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchpuppy.runtime.config import load_settings
from watchpuppy.runtime.pipeline import WatchPuppyRuntime

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run WatchPuppy pipeline only when ONVIF events trigger.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--onvif-port", type=int, default=2020)
    parser.add_argument("--duration-seconds", type=int, default=300)
    parser.add_argument("--pull-timeout-seconds", type=int, default=5)
    parser.add_argument("--message-limit", type=int, default=20)
    parser.add_argument("--cooldown-seconds", type=int, default=20)
    parser.add_argument("--reconnect-delay-seconds", type=float, default=3.0)
    parser.add_argument("--pipeline-lock-file")
    parser.add_argument("--wsdl-dir")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    settings = load_settings(args.config)
    epoch = os.getenv("WATCHPUPPY_EPOCH", "RUN1").strip() or "RUN1"

    watchdog_root = settings.watchdog_root
    if str(watchdog_root) not in sys.path:
        sys.path.insert(0, str(watchdog_root))

    from app.core.config import load_settings as load_watchdog_settings  # type: ignore
    from app.onvif.events import decide_trigger, parse_notification_message, summarize_event  # type: ignore
    from app.onvif.probe import discover_wsdl_dir, resolve_probe_target  # type: ignore

    try:
        from onvif import ONVIFCamera
        from zeep.helpers import serialize_object
    except ImportError as exc:
        raise RuntimeError("ONVIF dependency is required.") from exc

    watchdog_settings = load_watchdog_settings(settings.watchdog_config)
    target = resolve_probe_target(watchdog_settings, args.camera_id)
    wsdl_dir = discover_wsdl_dir(args.wsdl_dir)

    camera = ONVIFCamera(
        target.host,
        args.onvif_port,
        target.username,
        target.password,
        str(wsdl_dir),
    )
    events_service = camera.create_events_service()
    pullpoint_service = _create_pullpoint_service(
        camera,
        events_service,
        serialize_object,
        max(1, args.duration_seconds),
        quiet=args.quiet,
    )
    runtime = WatchPuppyRuntime(settings=settings, epoch=epoch)

    last_trigger_at: dict[str, float] = {}
    total_messages = 0
    topic_counts: Counter[str] = Counter()
    trigger_counts: Counter[str] = Counter()
    deadline = None if args.duration_seconds <= 0 else time.monotonic() + args.duration_seconds
    try:
        while deadline is None or time.monotonic() < deadline:
            remaining_budget = args.pull_timeout_seconds
            if deadline is not None:
                remaining_budget = max(1, min(args.pull_timeout_seconds, int(deadline - time.monotonic())))
            try:
                response = pullpoint_service.PullMessages(
                    {"Timeout": f"PT{remaining_budget}S", "MessageLimit": args.message_limit}
                )
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                if not args.quiet:
                    print(
                        json.dumps(
                            {
                                "camera_id": args.camera_id,
                                "warning": "pull_messages_failed",
                                "error": str(exc),
                                "action": "resubscribe",
                            },
                            indent=2,
                        ),
                        flush=True,
                    )
                time.sleep(max(0.0, args.reconnect_delay_seconds))
                pullpoint_service = _create_pullpoint_service(
                    camera,
                    events_service,
                    serialize_object,
                    max(1, args.duration_seconds),
                    quiet=args.quiet,
                )
                continue

            serialized = serialize_object(response)
            messages = serialized.get("NotificationMessage") or []
            for message in messages:
                total_messages += 1
                event = parse_notification_message(message)
                topic_counts[event.topic] += 1
                decision = decide_trigger(event)
                if not decision.should_trigger or not decision.trigger_key:
                    continue
                now = time.monotonic()
                last_seen = last_trigger_at.get(decision.trigger_key)
                if last_seen is not None and now - last_seen < args.cooldown_seconds:
                    continue
                last_trigger_at[decision.trigger_key] = now
                trigger_counts[decision.trigger_key] += 1
                if not args.quiet:
                    print(
                        json.dumps(
                            {
                                "camera_id": args.camera_id,
                                "trigger_key": decision.trigger_key,
                                "reason": decision.reason,
                                "event": summarize_event(event),
                                "epoch": epoch,
                            },
                            indent=2,
                        ),
                        flush=True,
                    )
                with _pipeline_lock(args.pipeline_lock_file):
                    runtime.run_capture_and_infer(args.camera_id)
        if not args.quiet:
            print(
                json.dumps(
                    {
                        "camera_id": args.camera_id,
                        "summary": {
                            "epoch": epoch,
                            "total_messages": total_messages,
                            "topic_counts": dict(topic_counts),
                            "trigger_counts": dict(trigger_counts),
                        },
                    },
                    indent=2,
                ),
                flush=True,
            )
    finally:
        runtime.close()
        try:
            pullpoint_service.Unsubscribe()
        except Exception:
            logger.debug("pullpoint unsubscribe failed", exc_info=True)


def _extract_subscription_xaddr(subscription_data: dict[str, object]) -> str:
    reference = subscription_data.get("SubscriptionReference") or {}
    address = reference.get("Address") if isinstance(reference, dict) else None
    if isinstance(address, dict):
        address = address.get("_value_1")
    if isinstance(address, list):
        address = address[0] if address else None
    if not address:
        raise RuntimeError(f"unable to extract PullPoint subscription address: {subscription_data}")
    return str(address)


def _create_pullpoint_service(camera, events_service, serialize_object, duration_seconds: int, *, quiet: bool):
    subscription = events_service.CreatePullPointSubscription(
        {"InitialTerminationTime": f"PT{duration_seconds}S"}
    )
    subscription_data = serialize_object(subscription)
    subscription_xaddr = _extract_subscription_xaddr(subscription_data)
    if not quiet:
        print(json.dumps({"subscription_xaddr": subscription_xaddr}, indent=2), flush=True)
    camera.xaddrs["http://www.onvif.org/ver10/events/wsdl/PullPointSubscription"] = subscription_xaddr
    return camera.create_pullpoint_service()


@contextmanager
def _pipeline_lock(lock_path: str | None):
    if not lock_path:
        yield
        return
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


if __name__ == "__main__":
    main()
