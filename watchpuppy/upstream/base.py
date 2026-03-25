from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from watchpuppy.types import SnapshotRecord


class SnapshotUpstream(Protocol):
    """Connector that yields snapshot records to downstream dataset/runtime code."""

    def iter_records(self) -> Iterable[SnapshotRecord]:
        ...
