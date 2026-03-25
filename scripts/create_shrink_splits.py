#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create split manifests that point to YOLO-shrink snapshot paths."
    )
    parser.add_argument(
        "--input-dir",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/splits",
        help="Directory containing the baseline train/val/test CSV manifests.",
    )
    parser.add_argument(
        "--output-dir",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/splits_shrink",
        help="Directory where shrink-based train/val/test CSV manifests will be written.",
    )
    parser.add_argument(
        "--from-root",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/raw/watchdog_snapshots",
        help="Original snapshot root prefix to replace.",
    )
    parser.add_argument(
        "--to-root",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/raw/watchdog_snapshots_shrink",
        help="Shrink snapshot root prefix to use.",
    )
    return parser


def rewrite_split(input_path: Path, output_path: Path, from_root: Path, to_root: Path) -> dict[str, int | str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows_out: list[dict[str, str]] = []
    missing = 0
    positives = 0
    with input_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            src_path = Path(row["image_path"])
            try:
                relative = src_path.relative_to(from_root)
            except ValueError as exc:
                raise ValueError(f"{src_path} does not live under {from_root}") from exc
            shrink_path = to_root / relative
            row["image_path"] = str(shrink_path)
            if not shrink_path.exists():
                missing += 1
            positives += int(row["label"])
            rows_out.append(row)

    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    return {
        "manifest_path": str(output_path),
        "rows": len(rows_out),
        "positives": positives,
        "negatives": len(rows_out) - positives,
        "missing_paths": missing,
    }


def main() -> None:
    args = build_parser().parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    from_root = Path(args.from_root)
    to_root = Path(args.to_root)

    summaries = []
    for split_name in ("train", "val", "test"):
        summary = rewrite_split(
            input_dir / f"{split_name}.csv",
            output_dir / f"{split_name}.csv",
            from_root=from_root,
            to_root=to_root,
        )
        summary["split"] = split_name
        summaries.append(summary)

    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
