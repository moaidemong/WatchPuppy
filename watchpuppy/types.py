from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SnapshotRecord:
    event_id: str
    snapshot_path: Path
    source_label: str | None = None
    binary_label: str | None = None
    epoch: str | None = None
    camera_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
