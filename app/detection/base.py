from __future__ import annotations

from app.core.schemas import Detection
from app.ingest.frame_source import Frame


class DogDetector:
    def detect(self, frame: Frame) -> list[Detection]:
        raise NotImplementedError
