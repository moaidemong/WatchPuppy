from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

from watchpuppy.datasets.binary import BinarySnapshotDatasetEntry


@dataclass(frozen=True)
class SplitManifestSummary:
    split_name: str
    row_count: int
    positives: int
    negatives: int
    manifest_path: Path


def write_stratified_split_manifests(
    entries: list[BinarySnapshotDatasetEntry],
    output_dir: Path,
    seed: int = 42,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> list[SplitManifestSummary]:
    if not entries:
        raise ValueError("entries must not be empty")
    if round(train_ratio + val_ratio + test_ratio, 6) != 1.0:
        raise ValueError("split ratios must sum to 1.0")

    rng = random.Random(seed)
    positives = [entry for entry in entries if entry.label == 1]
    negatives = [entry for entry in entries if entry.label == 0]
    rng.shuffle(positives)
    rng.shuffle(negatives)

    split_buckets = {
        "train": [],
        "val": [],
        "test": [],
    }
    for label_entries in (positives, negatives):
        train_end, val_end = _split_indices(len(label_entries), train_ratio, val_ratio)
        split_buckets["train"].extend(label_entries[:train_end])
        split_buckets["val"].extend(label_entries[train_end:val_end])
        split_buckets["test"].extend(label_entries[val_end:])

    output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[SplitManifestSummary] = []
    for split_name, split_entries in split_buckets.items():
        split_entries.sort(key=lambda item: item.event_id)
        manifest_path = output_dir / f"{split_name}.csv"
        _write_split_manifest(split_entries, manifest_path)
        positives_count = sum(entry.label for entry in split_entries)
        summaries.append(
            SplitManifestSummary(
                split_name=split_name,
                row_count=len(split_entries),
                positives=positives_count,
                negatives=len(split_entries) - positives_count,
                manifest_path=manifest_path,
            )
        )
    return summaries


def _split_indices(total: int, train_ratio: float, val_ratio: float) -> tuple[int, int]:
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)
    return train_end, val_end


def _write_split_manifest(entries: list[BinarySnapshotDatasetEntry], manifest_path: Path) -> None:
    fieldnames = ["event_id", "image_path", "label", "label_name", "epoch"]
    with manifest_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "event_id": entry.event_id,
                    "image_path": str(entry.image_path),
                    "label": entry.label,
                    "label_name": entry.label_name,
                    "epoch": entry.epoch or "",
                }
            )
