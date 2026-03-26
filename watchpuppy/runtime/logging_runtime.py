from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime
import logging
import os
from pathlib import Path
import sys
import threading
from typing import TextIO
from uuid import uuid4


_transaction_id_var: ContextVar[str] = ContextVar("watchpuppy_transaction_id", default="-")
_TRANSACTION_ID_WIDTH = 12


class TransactionContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        transaction_id = _transaction_id_var.get("-")
        if transaction_id == "-":
            transaction_id = "-" * _TRANSACTION_ID_WIDTH
        record.transaction_id = transaction_id
        return True


class DailyFileHandler(logging.Handler):
    def __init__(self, log_dir: Path, stem: str, level: int = logging.NOTSET) -> None:
        super().__init__(level=level)
        self._log_dir = Path(log_dir)
        self._stem = stem
        self._current_date = ""
        self._stream: TextIO | None = None
        self._lock = threading.RLock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            with self._lock:
                self._ensure_stream()
                assert self._stream is not None
                self._stream.write(message + "\n")
                self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        with self._lock:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        super().close()

    def _ensure_stream(self) -> None:
        today = datetime.now().strftime("%Y%m%d")
        if self._stream is not None and self._current_date == today:
            return
        if self._stream is not None:
            self._stream.close()
        self._log_dir.mkdir(parents=True, exist_ok=True)
        path = self._log_dir / f"{self._stem}-{today}.log"
        self._stream = path.open("a", encoding="utf-8")
        self._current_date = today


def configure_watchpuppy_logging() -> None:
    mode = os.getenv("WATCHPUPPY_LOG_MODE", "prod").strip().lower() or "prod"
    level = logging.DEBUG if mode == "debug" else logging.INFO
    log_dir = Path(
        os.getenv(
            "WATCHPUPPY_LOG_DIR",
            "/home/moai/Workspace/Codex/WatchPuppy/logs",
        )
    ).resolve()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [trx:%(transaction_id)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    context_filter = TransactionContextFilter()

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)
    root.addHandler(console_handler)

    backbone_handler = DailyFileHandler(log_dir, "backbone", level=level)
    backbone_handler.setFormatter(formatter)
    backbone_handler.addFilter(context_filter)
    root.addHandler(backbone_handler)

    for logger_name, stem in (
        ("watchpuppy.front_yolo_process", "front_yolo_process"),
        ("watchpuppy.backend_cnn_process", "backend_cnn_process"),
    ):
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.handlers.clear()
        logger.propagate = True
        handler = DailyFileHandler(log_dir, stem, level=level)
        handler.setFormatter(formatter)
        handler.addFilter(context_filter)
        logger.addHandler(handler)


def current_transaction_id() -> str:
    return _transaction_id_var.get("-")


def new_transaction_id(camera_id: str) -> str:
    return f"{camera_id}-{uuid4().hex[:10]}"


@contextmanager
def transaction_logging(transaction_id: str):
    token: Token[str] = _transaction_id_var.set(transaction_id)
    try:
        yield
    finally:
        _transaction_id_var.reset(token)
