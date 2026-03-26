from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import yaml


@dataclass(slots=True)
class StorageSettings:
    artifacts_dir: Path
    review_queue_dir: Path
    exports_dir: Path


@dataclass(slots=True)
class IngestSettings:
    backend: str
    camera_id: str
    camera_index: int
    device_path: str | None
    rtsp_url: str | None
    sample_fps: float
    max_frames: int | None
    frame_width: int | None
    frame_height: int | None


@dataclass(slots=True)
class CameraSettings:
    camera_id: str
    rtsp_url: str
    aliases: list[str]
    enabled: bool = True


@dataclass(slots=True)
class DetectionSettings:
    backend: str
    confidence_threshold: float
    model_path: str | None
    config_path: str | None
    labels_path: str | None
    dog_class_names: list[str]
    context_class_names: list[str]
    input_width: int
    input_height: int
    scale_factor: float
    swap_rb: bool
    stream_interface: str


@dataclass(slots=True)
class MotionGateSettings:
    enabled: bool
    roi: tuple[float, float, float, float] | None
    pixel_diff_threshold: float
    min_changed_ratio: float


@dataclass(slots=True)
class PipelineSettings:
    frame_window_size: int
    detector_confidence_threshold: float
    event_gap_seconds: float
    min_event_seconds: float
    alert_cooldown_seconds: float
    enable_clip_capture: bool


@dataclass(slots=True)
class RuleSettings:
    failed_attempt_min_attempts: int
    failed_attempt_min_duration_seconds: float
    min_body_lift_ratio: float
    max_progress_ratio: float


@dataclass(slots=True)
class TelegramSettings:
    bot_token_env: str
    chat_id_env: str


@dataclass(slots=True)
class NotifierSettings:
    backend: str
    telegram: TelegramSettings


@dataclass(slots=True)
class Settings:
    app_name: str
    storage: StorageSettings
    ingest: IngestSettings
    cameras: list[CameraSettings]
    detection: DetectionSettings
    motion_gate: MotionGateSettings
    pipeline: PipelineSettings
    rules: RuleSettings
    notifier: NotifierSettings


def _read_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(path: str | Path) -> Settings:
    raw = _read_yaml(path)
    storage = raw["storage"]
    ingest = raw.get("ingest", {})
    cameras = raw.get("cameras", [])
    detection = raw.get("detection", {})
    motion_gate = raw.get("motion_gate", {})
    pipeline = raw["pipeline"]
    rules = raw["rules"]
    notifier = raw["notifier"]
    return Settings(
        app_name=raw.get("app_name", "dog-rise-alert"),
        storage=StorageSettings(
            artifacts_dir=Path(storage["artifacts_dir"]),
            review_queue_dir=Path(storage["review_queue_dir"]),
            exports_dir=Path(storage["exports_dir"]),
        ),
        ingest=IngestSettings(
            backend=ingest.get("backend", "mock"),
            camera_id=ingest.get("camera_id", "default"),
            camera_index=ingest.get("camera_index", 0),
            device_path=ingest.get("device_path"),
            rtsp_url=_expand_env(ingest.get("rtsp_url")),
            sample_fps=ingest.get("sample_fps", 2.0),
            max_frames=ingest.get("max_frames", 60),
            frame_width=ingest.get("frame_width"),
            frame_height=ingest.get("frame_height"),
        ),
        cameras=[
            CameraSettings(
                camera_id=item["camera_id"],
                rtsp_url=_expand_env(item["rtsp_url"]),
                aliases=[str(alias) for alias in item.get("aliases", [])],
                enabled=item.get("enabled", True),
            )
            for item in cameras
        ],
        detection=DetectionSettings(
            backend=detection.get("backend", "mock"),
            confidence_threshold=detection.get("confidence_threshold", 0.5),
            model_path=detection.get("model_path"),
            config_path=detection.get("config_path"),
            labels_path=detection.get("labels_path"),
            dog_class_names=detection.get("dog_class_names", ["dog"]),
            context_class_names=detection.get("context_class_names", ["person", "cat"]),
            input_width=detection.get("input_width", 640),
            input_height=detection.get("input_height", 640),
            scale_factor=detection.get("scale_factor", 1.0 / 255.0),
            swap_rb=detection.get("swap_rb", True),
            stream_interface=detection.get("stream_interface", "PCIe"),
        ),
        motion_gate=MotionGateSettings(
            enabled=motion_gate.get("enabled", False),
            roi=_parse_roi(motion_gate.get("roi")),
            pixel_diff_threshold=motion_gate.get("pixel_diff_threshold", 25.0),
            min_changed_ratio=motion_gate.get("min_changed_ratio", 0.01),
        ),
        pipeline=PipelineSettings(**pipeline),
        rules=RuleSettings(**rules),
        notifier=NotifierSettings(
            backend=notifier["backend"],
            telegram=TelegramSettings(**notifier["telegram"]),
        ),
    )


def _parse_roi(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, list | tuple) or len(value) != 4:
        raise ValueError("motion_gate.roi must be a sequence of four floats")
    x1, y1, x2, y2 = (float(item) for item in value)
    return (x1, y1, x2, y2)


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value
