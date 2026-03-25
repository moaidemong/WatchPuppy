from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from watchpuppy.types import SnapshotRecord
from watchpuppy.upstream.base import SnapshotUpstream

if TYPE_CHECKING:
    from PIL.Image import Image


@dataclass(frozen=True)
class BinarySnapshotDatasetEntry:
    event_id: str
    image_path: Path
    label: int
    label_name: str
    epoch: str | None


def _label_to_int(label_name: str | None) -> int:
    return 1 if label_name == "failed_get_up_attempt" else 0


def load_binary_snapshot_dataset(upstream: SnapshotUpstream) -> list[BinarySnapshotDatasetEntry]:
    entries: list[BinarySnapshotDatasetEntry] = []
    for record in upstream.iter_records():
        entries.append(_from_record(record))
    return entries


def _from_record(record: SnapshotRecord) -> BinarySnapshotDatasetEntry:
    label_name = record.binary_label or "non_target"
    return BinarySnapshotDatasetEntry(
        event_id=record.event_id,
        image_path=record.snapshot_path,
        label=_label_to_int(label_name),
        label_name=label_name,
        epoch=record.epoch,
    )


def load_binary_snapshot_entries_from_manifest(
    manifest_path: Path,
    data_root: Path | None = None,
) -> list[BinarySnapshotDatasetEntry]:
    entries: list[BinarySnapshotDatasetEntry] = []
    with manifest_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            image_path = Path(row["image_path"])
            if data_root is not None and not image_path.is_absolute():
                image_path = data_root / image_path
            entries.append(
                BinarySnapshotDatasetEntry(
                    event_id=row["event_id"],
                    image_path=image_path,
                    label=int(row["label"]),
                    label_name=row["label_name"],
                    epoch=row.get("epoch") or None,
                )
            )
    return entries


class BinarySnapshotImageDataset:
    """Lightweight dataset wrapper for snapshot classification experiments."""

    def __init__(
        self,
        entries: list[BinarySnapshotDatasetEntry],
        transform: Callable[["Image"], object] | None = None,
    ) -> None:
        self.entries = entries
        self.transform = transform

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int) -> tuple[object, int, BinarySnapshotDatasetEntry]:
        from PIL import Image

        entry = self.entries[index]
        image = Image.open(entry.image_path).convert("RGB")
        if self.transform is not None:
            image = self.transform(image)
        return image, entry.label, entry
