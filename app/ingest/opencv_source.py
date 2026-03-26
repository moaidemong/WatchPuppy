from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable

from app.ingest.frame_source import Frame, FrameSource

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenCVFrameSourceConfig:
    camera_index: int = 0
    device_path: str | None = None
    rtsp_url: str | None = None
    sample_fps: float = 2.0
    max_frames: int | None = None
    camera_id: str = "opencv-camera"


class OpenCVFrameSource(FrameSource):
    """Read frames from a local camera device via OpenCV VideoCapture."""

    def __init__(self, config: OpenCVFrameSourceConfig) -> None:
        if config.sample_fps <= 0:
            raise ValueError("sample_fps must be greater than zero")
        self.config = config

    def _open_capture(self):
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - depends on runtime environment
            raise RuntimeError(
                "OpenCV is required for the 'opencv' ingest backend. "
                "Install the 'cv2' package in the runtime environment."
            ) from exc

        if self.config.rtsp_url:
            source = self.config.rtsp_url
        else:
            source = self.config.device_path if self.config.device_path else self.config.camera_index
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"failed to open video source: {source}")
        return capture

    def read_frames(self) -> Iterable[Frame]:
        capture = self._open_capture()
        start_time = time.monotonic()
        emitted_frames = 0
        next_sample_deadline = start_time

        try:
            while self.config.max_frames is None or emitted_frames < self.config.max_frames:
                ok, image = capture.read()
                if not ok:
                    logger.warning("camera read failed after %s emitted frames", emitted_frames)
                    break

                now = time.monotonic()
                if now < next_sample_deadline:
                    continue

                yield Frame(
                    index=emitted_frames,
                    timestamp_s=now - start_time,
                    camera_id=self.config.camera_id,
                    payload=image,
                )
                emitted_frames += 1
                next_sample_deadline = now + (1.0 / self.config.sample_fps)
        finally:
            capture.release()
