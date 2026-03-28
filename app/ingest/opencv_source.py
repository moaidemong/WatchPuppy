from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable
import atexit

from app.ingest.frame_source import Frame, FrameSource

logger = logging.getLogger(__name__)

_SHARED_CAPTURES: dict[str, object] = {}


@dataclass(slots=True)
class OpenCVFrameSourceConfig:
    camera_index: int = 0
    device_path: str | None = None
    rtsp_url: str | None = None
    persistent_connection: bool = False
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
        source_key = str(source)
        if self.config.persistent_connection:
            shared = _SHARED_CAPTURES.get(source_key)
            if shared is not None:
                return shared
        capture = cv2.VideoCapture(source)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"failed to open video source: {source}")
        if self.config.persistent_connection:
            _SHARED_CAPTURES[source_key] = capture
        return capture

    def read_frames(self) -> Iterable[Frame]:
        capture = self._open_capture()
        start_time = time.monotonic()
        emitted_frames = 0
        next_sample_deadline = start_time

        try:
            if self.config.persistent_connection:
                # Drain a few buffered packets so the first emitted frame is as fresh as possible.
                for _ in range(4):
                    capture.grab()
            while self.config.max_frames is None or emitted_frames < self.config.max_frames:
                ok, image = capture.read()
                if not ok:
                    logger.warning("camera read failed after %s emitted frames", emitted_frames)
                    if self.config.persistent_connection:
                        self._reset_shared_capture(capture)
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
            if not self.config.persistent_connection:
                capture.release()

    def close(self) -> None:
        if self.config.persistent_connection:
            return

    def _reset_shared_capture(self, capture) -> None:
        try:
            capture.release()
        except Exception:
            logger.debug("failed to release broken shared capture", exc_info=True)
        source = self.config.rtsp_url if self.config.rtsp_url else (
            self.config.device_path if self.config.device_path else self.config.camera_index
        )
        _SHARED_CAPTURES.pop(str(source), None)


def _release_shared_captures() -> None:
    for capture in _SHARED_CAPTURES.values():
        try:
            capture.release()
        except Exception:
            logger.debug("failed to release shared capture", exc_info=True)
    _SHARED_CAPTURES.clear()


atexit.register(_release_shared_captures)
