from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.core.schemas import Detection


@dataclass(slots=True)
class Frame:
    index: int
    timestamp_s: float
    camera_id: str = "default"
    payload: object | None = None
    detections: list[Detection] = field(default_factory=list)


class FrameSource:
    def read_frames(self) -> Iterable[Frame]:
        raise NotImplementedError
