from __future__ import annotations

from pathlib import Path

from watchpuppy.runtime.logging_runtime import configure_watchpuppy_logging

def configure_logging(config_path: str | Path = "configs/logging.yaml") -> None:
    _ = Path(config_path)
    configure_watchpuppy_logging()
