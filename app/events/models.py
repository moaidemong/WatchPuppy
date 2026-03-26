from __future__ import annotations

from dataclasses import dataclass, field
from app.ingest.frame_source import Frame


@dataclass(slots=True)
class EventWindow:
    event_id: str
    start_s: float
    end_s: float
    camera_id: str = "default"
    frames: list[Frame] = field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)
