#!/home/moai/Workspace/Codex/Runtime/Hailo/.venv/bin/python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

from app.core.config import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Print WatchPuppy camera RTSP URL.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--camera-id", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    with config_path.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}
    app_config_path = Path(raw.get("watchdog_config", config_path))
    settings = load_settings(app_config_path)
    for camera in settings.cameras:
        if camera.camera_id == args.camera_id or args.camera_id in camera.aliases:
            print(camera.rtsp_url)
            return
    raise SystemExit(f"camera_id not found: {args.camera_id}")


if __name__ == "__main__":
    main()
