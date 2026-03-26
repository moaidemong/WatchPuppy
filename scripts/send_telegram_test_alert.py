#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchpuppy.runtime.notifier import send_failed_get_up_alert


DEFAULT_ENV_PATH = Path("/home/moai/Workspace/Codex/WatchPuppy/configs/watchpuppy.env")
DEFAULT_IMAGE_PATH = Path(
    "/home/moai/Workspace/Codex/WatchPuppy/artifacts/RUN1__a-0000006498-0001__20260326T083630767904Z__a-0e500221c3/snapshot.jpg"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a WatchPuppy Telegram alert test.")
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_PATH),
        help="Path to env file with WATCHPUPPY_TELEGRAM_* settings",
    )
    parser.add_argument(
        "--image-path",
        default=str(DEFAULT_IMAGE_PATH),
        help="Snapshot image path to attach",
    )
    parser.add_argument("--event-id", default="telegram-image-test", help="Event id shown in message")
    parser.add_argument("--camera-id", default="test", help="Camera id shown in message")
    parser.add_argument("--epoch", default="RUN1", help="Epoch shown in message")
    parser.add_argument("--score", type=float, default=0.999, help="Score shown in message")
    parser.add_argument("--threshold", type=float, default=0.8, help="Threshold shown in message")
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    args = parse_args()
    load_env_file(Path(args.env_file))
    result = send_failed_get_up_alert(
        event_id=args.event_id,
        camera_id=args.camera_id,
        epoch=args.epoch,
        score=args.score,
        threshold=args.threshold,
        snapshot_path=Path(args.image_path),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
