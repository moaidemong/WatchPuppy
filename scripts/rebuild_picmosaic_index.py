#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchpuppy.runtime.picmosaic_meta import rebuild_picmosaic_index_bulk


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild and normalize WatchPuppy picmosaic-index.json.")
    parser.add_argument(
        "--artifacts-root",
        default="/home/moai/Workspace/Codex/WatchPuppy/artifacts",
        help="WatchPuppy artifacts root",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rebuild_picmosaic_index_bulk(Path(args.artifacts_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
