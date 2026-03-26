from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(slots=True)
class Detection:
    label: str
    confidence: float
    bbox: BoundingBox


@dataclass(slots=True)
class Keypoint:
    name: str
    x: float
    y: float
    confidence: float


@dataclass(slots=True)
class PoseFrame:
    timestamp_s: float
    keypoints: list[Keypoint] = field(default_factory=list)


@dataclass(slots=True)
class EventFeatureVector:
    event_id: str
    duration_s: float
    attempt_count: int
    body_lift_ratio: float
    progress_ratio: float
    pose_confidence_mean: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
