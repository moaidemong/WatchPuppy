#!/home/moai/Workspace/Codex/Runtime/Hailo/.venv/bin/python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from watchpuppy.runtime.logging_runtime import configure_watchpuppy_logging
from watchpuppy.streaming import run_mjpeg_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run WatchPuppy per-camera MJPEG stream server.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    configure_watchpuppy_logging()
    run_mjpeg_server(
        config_path=Path(args.config),
        camera_id=args.camera_id,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
