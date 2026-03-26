from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

from app.ingest.frame_source import Frame, FrameSource


@dataclass(slots=True)
class Picamera2FrameSourceConfig:
    sample_fps: float = 1.0
    max_frames: int | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    camera_id: str = "picamera2-camera"


class Picamera2FrameSource(FrameSource):
    """Read frames from Raspberry Pi Camera Module via Picamera2."""

    def __init__(self, config: Picamera2FrameSourceConfig) -> None:
        if config.sample_fps <= 0:
            raise ValueError("sample_fps must be greater than zero")
        self.config = config

    def _build_camera(self):
        try:
            from picamera2 import Picamera2
        except ImportError as exc:  # pragma: no cover - runtime dependent
            raise RuntimeError(
                "Picamera2 is required for the 'picamera2' ingest backend. "
                "Install it in the active Python environment."
            ) from exc

        camera = Picamera2()
        main_config: dict[str, tuple[int, int]] = {}
        if self.config.frame_width and self.config.frame_height:
            main_config["size"] = (self.config.frame_width, self.config.frame_height)
        preview_config = camera.create_preview_configuration(main=main_config or None)
        camera.configure(preview_config)
        return camera

    def read_frames(self) -> Iterable[Frame]:
        camera = self._build_camera()
        start_time = time.monotonic()
        emitted_frames = 0
        next_sample_deadline = start_time

        camera.start()
        try:
            time.sleep(0.5)
            while self.config.max_frames is None or emitted_frames < self.config.max_frames:
                now = time.monotonic()
                if now < next_sample_deadline:
                    time.sleep(min(0.01, next_sample_deadline - now))
                    continue

                image = camera.capture_array()
                yield Frame(
                    index=emitted_frames,
                    timestamp_s=now - start_time,
                    camera_id=self.config.camera_id,
                    payload=image,
                )
                emitted_frames += 1
                next_sample_deadline = now + (1.0 / self.config.sample_fps)
        finally:
            camera.stop()
