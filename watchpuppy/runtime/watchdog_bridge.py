from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


def run_watchdog_capture_once(
    *,
    watchdog_root: Path,
    watchdog_config: Path,
    camera_id: str,
    epoch: str,
    transaction_id: str | None,
    artifacts_dir: Path,
    review_queue_dir: Path,
    exports_dir: Path,
) -> list[Path]:
    from app.core.config import load_settings
    from app.pipeline.orchestrator import PipelineOrchestrator

    with _pushd(watchdog_root):
        settings = load_settings(watchdog_config)
        settings.ingest.camera_id = camera_id
        settings.storage.artifacts_dir = artifacts_dir
        settings.storage.review_queue_dir = review_queue_dir
        settings.storage.exports_dir = exports_dir
        with _temporary_env(
            WATCHPUPPY_EVENT_EPOCH=epoch,
            WATCHPUPPY_EVENT_TRANSACTION_ID=transaction_id or "",
        ):
            before = {path.resolve() for path in artifacts_dir.glob("*/metadata.json")}
            orchestrator = PipelineOrchestrator.from_settings(settings)
            try:
                orchestrator.run_once()
            finally:
                detector = getattr(orchestrator, "detector", None)
                if detector is not None and hasattr(detector, "close"):
                    detector.close()
                frame_source = getattr(orchestrator, "frame_source", None)
                if frame_source is not None and hasattr(frame_source, "close"):
                    frame_source.close()
            after = {path.resolve() for path in artifacts_dir.glob("*/metadata.json")}
    return sorted(after - before)


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


@contextmanager
def _temporary_env(**values: str):
    previous = {key: os.environ.get(key) for key in values}
    for key, value in values.items():
        os.environ[key] = value
    try:
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
