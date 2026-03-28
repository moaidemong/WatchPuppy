from __future__ import annotations

from app.core.config import CameraSettings, IngestSettings
from app.ingest.frame_source import FrameSource
from app.ingest.mock_source import MockFrameSource
from app.ingest.opencv_source import OpenCVFrameSource, OpenCVFrameSourceConfig
from app.ingest.picamera2_source import Picamera2FrameSource, Picamera2FrameSourceConfig


def build_frame_source(settings: IngestSettings, cameras: list[CameraSettings] | None = None) -> FrameSource:
    if settings.backend == "mock":
        total_frames = settings.max_frames if settings.max_frames is not None else 60
        return MockFrameSource(total_frames=total_frames, fps=settings.sample_fps, camera_id=settings.camera_id)

    if settings.backend == "opencv":
        selected_camera = _select_camera(settings.camera_id, cameras or [])
        return OpenCVFrameSource(
            OpenCVFrameSourceConfig(
                camera_index=settings.camera_index,
                device_path=settings.device_path,
                rtsp_url=selected_camera.rtsp_url if selected_camera else settings.rtsp_url,
                persistent_connection=settings.persistent_connection,
                sample_fps=settings.sample_fps,
                max_frames=settings.max_frames,
                camera_id=(selected_camera.camera_id if selected_camera else settings.camera_id),
            )
        )

    if settings.backend == "picamera2":
        return Picamera2FrameSource(
            Picamera2FrameSourceConfig(
                sample_fps=settings.sample_fps,
                max_frames=settings.max_frames,
                frame_width=settings.frame_width,
                frame_height=settings.frame_height,
                camera_id=settings.camera_id,
            )
        )

    raise ValueError(f"unsupported ingest backend: {settings.backend}")


def _select_camera(camera_id: str, cameras: list[CameraSettings]) -> CameraSettings | None:
    for camera in cameras:
        if not camera.enabled:
            continue
        if camera.camera_id == camera_id or camera_id in camera.aliases:
            return camera
    return None
