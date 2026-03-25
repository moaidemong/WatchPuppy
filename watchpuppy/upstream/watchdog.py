from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from watchpuppy.types import SnapshotRecord


@dataclass(frozen=True)
class WatchDogManifestUpstream:
    """Offline connector backed by a WatchDog-derived CSV manifest."""

    manifest_path: Path
    data_root: Path

    def iter_records(self) -> list[SnapshotRecord]:
        records: list[SnapshotRecord] = []
        with self.manifest_path.open("r", encoding="utf-8", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                snapshot_rel = row["snapshot_path"]
                records.append(
                    SnapshotRecord(
                        event_id=row["event_id"],
                        snapshot_path=self.data_root / snapshot_rel,
                        source_label=row.get("source_review_label"),
                        binary_label=row.get("binary_label"),
                        epoch=row.get("epoch"),
                        metadata={
                            "source_snapshot_path": row.get("source_snapshot_path", ""),
                        },
                    )
                )
        return records
