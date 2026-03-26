from __future__ import annotations

from typing import Iterable
from app.ingest.frame_source import Frame, FrameSource


class MockFrameSource(FrameSource):
    def __init__(self, total_frames: int = 60, fps: float = 2.0, camera_id: str = "mock-camera") -> None:
        self.total_frames = total_frames
        self.fps = fps
        self.camera_id = camera_id

    def read_frames(self) -> Iterable[Frame]:
        for index in range(self.total_frames):
            yield Frame(index=index, timestamp_s=index / self.fps, camera_id=self.camera_id, payload=None)
