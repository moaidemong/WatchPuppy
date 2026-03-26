from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class RuntimeStorageSettings:
    artifacts_dir: Path
    review_queue_dir: Path
    exports_dir: Path
    shrink_dir: Path


@dataclass(slots=True)
class ReviewWebSettings:
    db_path: Path


@dataclass(slots=True)
class ModelRuntimeSettings:
    model_name: str
    model_path: Path
    image_size: int
    threshold: float
    server_url: str
    margin_ratio: float
    allowed_trigger_keys: list[str]
    allowed_detection_labels: list[str]
    block_on_context_labels: list[str]


@dataclass(slots=True)
class WatchPuppySettings:
    app_name: str
    watchdog_root: Path
    watchdog_config: Path
    storage: RuntimeStorageSettings
    review_web: ReviewWebSettings
    runtime: ModelRuntimeSettings


def load_settings(path: str | Path) -> WatchPuppySettings:
    raw = _read_yaml(path)
    storage = raw["storage"]
    review_web = raw["review_web"]
    runtime = raw["runtime"]
    return WatchPuppySettings(
        app_name=raw.get("app_name", "watchpuppy"),
        watchdog_root=Path(raw["watchdog_root"]).resolve(),
        watchdog_config=Path(raw["watchdog_config"]).resolve(),
        storage=RuntimeStorageSettings(
            artifacts_dir=Path(storage["artifacts_dir"]).resolve(),
            review_queue_dir=Path(storage["review_queue_dir"]).resolve(),
            exports_dir=Path(storage["exports_dir"]).resolve(),
            shrink_dir=Path(storage["shrink_dir"]).resolve(),
        ),
        review_web=ReviewWebSettings(
            db_path=Path(review_web["db_path"]).resolve(),
        ),
        runtime=ModelRuntimeSettings(
            model_name=str(runtime["model_name"]),
            model_path=Path(runtime["model_path"]).resolve(),
            image_size=int(runtime["image_size"]),
            threshold=float(runtime["threshold"]),
            server_url=str(runtime.get("server_url", "http://127.0.0.1:18021")).rstrip("/"),
            margin_ratio=float(runtime.get("margin_ratio", 0.2)),
            allowed_trigger_keys=[str(item) for item in runtime.get("allowed_trigger_keys", ["pet"])],
            allowed_detection_labels=[str(item) for item in runtime.get("allowed_detection_labels", ["dog"])],
            block_on_context_labels=[str(item) for item in runtime.get("block_on_context_labels", [])],
        ),
    )


def _read_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp) or {}
