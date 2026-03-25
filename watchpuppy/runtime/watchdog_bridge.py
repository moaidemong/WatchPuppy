from __future__ import annotations

import sys
from pathlib import Path


def run_watchdog_capture_once(
    *,
    watchdog_root: Path,
    watchdog_config: Path,
    camera_id: str,
    artifacts_dir: Path,
    review_queue_dir: Path,
    exports_dir: Path,
) -> list[Path]:
    if str(watchdog_root) not in sys.path:
        sys.path.insert(0, str(watchdog_root))

    from app.core.config import load_settings  # type: ignore
    from app.pipeline.orchestrator import PipelineOrchestrator  # type: ignore

    settings = load_settings(watchdog_config)
    settings.ingest.camera_id = camera_id
    settings.storage.artifacts_dir = artifacts_dir
    settings.storage.review_queue_dir = review_queue_dir
    settings.storage.exports_dir = exports_dir

    before = {path.resolve() for path in artifacts_dir.glob("*/metadata.json")}
    orchestrator = PipelineOrchestrator.from_settings(settings)
    orchestrator.run_once()
    after = {path.resolve() for path in artifacts_dir.glob("*/metadata.json")}
    return sorted(after - before)
