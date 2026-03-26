from __future__ import annotations

from app.core.schemas import BoundingBox, Detection
from app.detection.base import DogDetector
from app.ingest.frame_source import Frame


class MockDogDetector(DogDetector):
    """Always returns one dog detection in a fixed box for demo/testing."""

    def detect(self, frame: Frame) -> list[Detection]:
        return [
            Detection(
                label="dog",
                confidence=0.95,
                bbox=BoundingBox(x1=0.1, y1=0.2, x2=0.8, y2=0.9),
            )
        ]
