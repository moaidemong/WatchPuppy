from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from watchpuppy.types import SnapshotRecord
from watchpuppy.upstream.base import SnapshotUpstream


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
