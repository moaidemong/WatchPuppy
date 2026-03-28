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
from watchpuppy.runtime.logging_runtime import configure_watchpuppy_logging, new_transaction_id, transaction_logging
from watchpuppy.runtime.pipeline import WatchPuppyRuntime


logger = logging.getLogger("watchpuppy.backbone")


def main() -> None:
    configure_watchpuppy_logging()

    parser = argparse.ArgumentParser(description="Run WatchPuppy pipeline only when ONVIF events trigger.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--onvif-port", type=int, default=2020)
    parser.add_argument("--duration-seconds", type=int, default=300)
    parser.add_argument("--pull-timeout-seconds", type=int, default=5)
    parser.add_argument("--operation-timeout-seconds", type=float, default=15.0)
    parser.add_argument("--message-limit", type=int, default=20)
    parser.add_argument("--cooldown-seconds", type=int, default=20)
    parser.add_argument("--heartbeat-seconds", type=float, default=60.0)
    parser.add_argument("--reconnect-delay-seconds", type=float, default=3.0)
    parser.add_argument("--pipeline-lock-file")
    parser.add_argument("--wsdl-dir")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    settings = load_settings(args.config)
    epoch = os.getenv("WATCHPUPPY_EPOCH", "RUN1").strip() or "RUN1"
    allowed_trigger_keys = set(settings.runtime.allowed_trigger_keys)

    from app.core.config import load_settings as load_watchdog_settings
    from app.onvif.events import decide_trigger, parse_notification_message, summarize_event
    from app.onvif.probe import discover_wsdl_dir, resolve_probe_target

    try:
        from onvif import ONVIFCamera
        from zeep.helpers import serialize_object
        from zeep.transports import Transport
    except ImportError as exc:
        raise RuntimeError("ONVIF dependency is required.") from exc

    watchdog_settings = load_watchdog_settings(settings.watchdog_config)
    target = resolve_probe_target(watchdog_settings, args.camera_id)
    wsdl_dir = discover_wsdl_dir(args.wsdl_dir)

    runtime = WatchPuppyRuntime(settings=settings, epoch=epoch)
    transport = None
    camera = None
    events_service = None
    pullpoint_service = None
    transport, camera, events_service, pullpoint_service = _build_onvif_context(
        target=target,
        onvif_port=args.onvif_port,
        wsdl_dir=wsdl_dir,
        operation_timeout_seconds=max(float(args.pull_timeout_seconds) + 2.0, args.operation_timeout_seconds),
        duration_seconds=max(1, args.duration_seconds),
        reconnect_delay_seconds=max(0.0, args.reconnect_delay_seconds),
        camera_id=args.camera_id,
        quiet=args.quiet,
        ONVIFCamera=ONVIFCamera,
        Transport=Transport,
        serialize_object=serialize_object,
    )

    last_trigger_at: dict[str, float] = {}
    total_messages = 0
    topic_counts: Counter[str] = Counter()
    trigger_counts: Counter[str] = Counter()
    consecutive_pull_failures = 0
    last_pull_return_at = time.monotonic()
    last_pull_return_wallclock = _utc_now_iso()
    next_heartbeat_at = time.monotonic() + max(1.0, args.heartbeat_seconds)
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
                consecutive_pull_failures += 1
                if not args.quiet:
                    logger.warning(
                        json.dumps(
                            {
                                "camera_id": args.camera_id,
                                "warning": "pull_messages_failed",
                                "state": "degraded",
                                "consecutive_failures": consecutive_pull_failures,
                                "error": str(exc),
                                "action": "rebuild_and_resubscribe",
                            },
                            ensure_ascii=False,
                        )
                    )
                _close_pullpoint_service(pullpoint_service)
                _close_transport(transport)
                time.sleep(max(0.0, args.reconnect_delay_seconds))
                transport, camera, events_service, pullpoint_service = _build_onvif_context(
                    target=target,
                    onvif_port=args.onvif_port,
                    wsdl_dir=wsdl_dir,
                    operation_timeout_seconds=max(float(args.pull_timeout_seconds) + 2.0, args.operation_timeout_seconds),
                    duration_seconds=max(1, args.duration_seconds),
                    reconnect_delay_seconds=max(0.0, args.reconnect_delay_seconds),
                    camera_id=args.camera_id,
                    quiet=args.quiet,
                    ONVIFCamera=ONVIFCamera,
                    Transport=Transport,
                    serialize_object=serialize_object,
                )
                continue

            serialized = serialize_object(response)
            messages = serialized.get("NotificationMessage") or []
            last_pull_return_at = time.monotonic()
            last_pull_return_wallclock = _utc_now_iso()
            if consecutive_pull_failures > 0 and not args.quiet:
                logger.info(
                    json.dumps(
                        {
                            "camera_id": args.camera_id,
                            "state": "recovered",
                            "reason": "pull_messages_returned",
                            "recovered_after_failures": consecutive_pull_failures,
                        },
                        ensure_ascii=False,
                    )
                )
            consecutive_pull_failures = 0
            if not args.quiet and last_pull_return_at >= next_heartbeat_at:
                logger.info(
                    json.dumps(
                        {
                            "camera_id": args.camera_id,
                            "state": "connected",
                            "reason": "pull_heartbeat",
                            "last_pull_return_at": last_pull_return_wallclock,
                            "messages_in_batch": len(messages),
                            "total_messages": total_messages,
                            "trigger_counts": dict(trigger_counts),
                        },
                        ensure_ascii=False,
                    )
                )
                next_heartbeat_at = last_pull_return_at + max(1.0, args.heartbeat_seconds)
            for message in messages:
                total_messages += 1
                event = parse_notification_message(message)
                topic_counts[event.topic] += 1
                decision = decide_trigger(event)
                if not decision.should_trigger or not decision.trigger_key:
                    continue
                if decision.trigger_key not in allowed_trigger_keys:
                    continue
                now = time.monotonic()
                last_seen = last_trigger_at.get(decision.trigger_key)
                if last_seen is not None and now - last_seen < args.cooldown_seconds:
                    continue

                last_trigger_at[decision.trigger_key] = now
                trigger_counts[decision.trigger_key] += 1
                transaction_id = new_transaction_id(args.camera_id)
                with transaction_logging(transaction_id):
                    if not args.quiet:
                        logger.info(
                            json.dumps(
                                {
                                    "camera_id": args.camera_id,
                                    "transaction_id": transaction_id,
                                    "trigger_key": decision.trigger_key,
                                    "reason": decision.reason,
                                    "event": summarize_event(event),
                                    "epoch": epoch,
                                },
                                ensure_ascii=False,
                            )
                        )
                    with _pipeline_lock(args.pipeline_lock_file):
                        runtime.run_capture_and_infer(args.camera_id, transaction_id=transaction_id)

        if not args.quiet:
            logger.info(
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
                    ensure_ascii=False,
                )
            )
    finally:
        runtime.close()
        _close_pullpoint_service(pullpoint_service)
        _close_transport(transport)


def _build_onvif_context(
    *,
    target,
    onvif_port: int,
    wsdl_dir: Path,
    operation_timeout_seconds: float,
    duration_seconds: int,
    reconnect_delay_seconds: float,
    camera_id: str,
    quiet: bool,
    ONVIFCamera,
    Transport,
    serialize_object,
):
    transport = Transport(timeout=300, operation_timeout=operation_timeout_seconds)
    camera = ONVIFCamera(
        target.host,
        onvif_port,
        target.username,
        target.password,
        str(wsdl_dir),
        transport=transport,
    )
    events_service = camera.create_events_service()
    pullpoint_service = _create_pullpoint_service_with_retry(
        camera,
        events_service,
        serialize_object,
        duration_seconds,
        reconnect_delay_seconds=reconnect_delay_seconds,
        camera_id=camera_id,
        quiet=quiet,
    )
    return transport, camera, events_service, pullpoint_service


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
        logger.info(json.dumps({"subscription_xaddr": subscription_xaddr}, ensure_ascii=False))
    camera.xaddrs["http://www.onvif.org/ver10/events/wsdl/PullPointSubscription"] = subscription_xaddr
    return camera.create_pullpoint_service()


def _create_pullpoint_service_with_retry(
    camera,
    events_service,
    serialize_object,
    duration_seconds: int,
    *,
    reconnect_delay_seconds: float,
    camera_id: str,
    quiet: bool,
):
    consecutive_failures = 0
    while True:
        try:
            service = _create_pullpoint_service(
                camera,
                events_service,
                serialize_object,
                duration_seconds,
                quiet=quiet,
            )
            if not quiet and consecutive_failures > 0:
                logger.info(
                    json.dumps(
                        {
                            "camera_id": camera_id,
                            "state": "recovered",
                            "reason": "pullpoint_subscription_created",
                            "recovered_after_failures": consecutive_failures,
                        },
                        ensure_ascii=False,
                    )
                )
            return service
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            consecutive_failures += 1
            if not quiet:
                logger.warning(
                    json.dumps(
                        {
                            "camera_id": camera_id,
                            "warning": "create_pullpoint_subscription_failed",
                            "state": "degraded",
                            "consecutive_failures": consecutive_failures,
                            "error": str(exc),
                            "action": "retry",
                        },
                        ensure_ascii=False,
                    )
                )
            time.sleep(reconnect_delay_seconds)


def _close_pullpoint_service(pullpoint_service) -> None:
    if pullpoint_service is None:
        return
    try:
        pullpoint_service.Unsubscribe()
    except Exception:
        logger.debug("pullpoint unsubscribe failed", exc_info=True)


def _close_transport(transport) -> None:
    if transport is None:
        return
    try:
        transport.session.close()
    except Exception:
        logger.debug("transport session close failed", exc_info=True)


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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
