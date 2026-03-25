#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchpuppy.upstream.yolo_shrink import YoloShrinkConfig, write_yolo_shrink_snapshots


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate YOLO bbox shrink snapshots paired with imported WatchDog snapshots."
    )
    parser.add_argument(
        "--input-manifest-path",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/gen1_gen5_failed_get_up_binary.csv",
        help="Binary dataset CSV manifest path.",
    )
    parser.add_argument(
        "--output-root",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/raw/watchdog_snapshots_shrink",
        help="Output root for YOLO-cropped snapshots.",
    )
    parser.add_argument(
        "--report-path",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/yolo_shrink_report.csv",
        help="CSV report path for crop results.",
    )
    parser.add_argument(
        "--margin-ratio",
        type=float,
        default=0.20,
        help="Relative margin added around the detected dog bounding box.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    stats = write_yolo_shrink_snapshots(
        YoloShrinkConfig(
            input_manifest_path=Path(args.input_manifest_path),
            output_root=Path(args.output_root),
            report_path=Path(args.report_path),
            margin_ratio=args.margin_ratio,
        )
    )
    print(json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
