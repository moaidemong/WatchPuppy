#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchpuppy.data.import_watchdog import ImportConfig, import_watchdog_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import reviewed WatchDog snapshots into a local WatchPuppy binary dataset."
    )
    parser.add_argument(
        "--review-db",
        default="/home/moai/Workspace/Codex/WatchDog/review_web/data/review_web.sqlite3",
        help="Path to the WatchDog review_web SQLite database.",
    )
    parser.add_argument(
        "--watchdog-root",
        default="/home/moai/Workspace/Codex/WatchDog",
        help="WatchDog repository root used to resolve relative snapshot paths.",
    )
    parser.add_argument(
        "--output-root",
        default="/home/moai/Workspace/Codex/WatchPuppy/data",
        help="WatchPuppy data root.",
    )
    parser.add_argument(
        "--manifest-path",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/gen1_gen5_failed_get_up_binary.csv",
        help="Output CSV manifest path.",
    )
    parser.add_argument(
        "--epochs",
        nargs="+",
        default=["Gen1", "Gen2", "Gen3", "Gen4", "Gen5"],
        help="Approved review epochs to import.",
    )
    parser.add_argument(
        "--review-status",
        default="approved",
        help="Review status to include.",
    )
    parser.add_argument(
        "--link-mode",
        choices=["hardlink", "copy", "symlink"],
        default="hardlink",
        help="How to materialize snapshots inside WatchPuppy data/raw.",
    )
    parser.add_argument(
        "--excluded-event-ids-file",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/excluded_event_ids.txt",
        help="Optional newline-delimited event_id exclusion list.",
    )
    return parser


def load_excluded_event_ids(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def main() -> None:
    args = build_parser().parse_args()
    excluded_event_ids = load_excluded_event_ids(Path(args.excluded_event_ids_file))
    config = ImportConfig(
        review_db=Path(args.review_db),
        watchdog_root=Path(args.watchdog_root),
        output_root=Path(args.output_root),
        manifest_path=Path(args.manifest_path),
        epochs=tuple(args.epochs),
        review_status=args.review_status,
        link_mode=args.link_mode,
        excluded_event_ids=excluded_event_ids,
    )
    stats = import_watchdog_dataset(config)
    stats["excluded_event_ids"] = len(excluded_event_ids)
    print(json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
