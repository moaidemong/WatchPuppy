#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchpuppy.datasets import load_binary_snapshot_dataset, write_stratified_split_manifests
from watchpuppy.upstream import WatchDogManifestUpstream


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create stratified train/val/test split manifests from the binary snapshot dataset."
    )
    parser.add_argument(
        "--manifest-path",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/gen1_gen5_failed_get_up_binary.csv",
        help="Binary dataset CSV manifest path.",
    )
    parser.add_argument(
        "--data-root",
        default="/home/moai/Workspace/Codex/WatchPuppy/data",
        help="Data root used to resolve relative image paths.",
    )
    parser.add_argument(
        "--output-dir",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/splits",
        help="Directory where split CSVs will be written.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    upstream = WatchDogManifestUpstream(
        manifest_path=Path(args.manifest_path),
        data_root=Path(args.data_root),
    )
    entries = load_binary_snapshot_dataset(upstream)
    summaries = write_stratified_split_manifests(
        entries=entries,
        output_dir=Path(args.output_dir),
        seed=args.seed,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
    )
    print(
        json.dumps(
            [
                {
                    "split": summary.split_name,
                    "rows": summary.row_count,
                    "positives": summary.positives,
                    "negatives": summary.negatives,
                    "manifest_path": str(summary.manifest_path),
                }
                for summary in summaries
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
