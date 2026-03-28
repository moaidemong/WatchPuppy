from __future__ import annotations

import logging
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import yaml

from app.core.config import load_settings

logger = logging.getLogger("watchpuppy.backbone")


class _LatestFrameBuffer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: bytes | None = None
        self._updated_at = 0.0

    def update(self, frame: bytes) -> None:
        with self._lock:
            self._frame = frame
            self._updated_at = time.time()

    def snapshot(self) -> tuple[bytes | None, float]:
        with self._lock:
            return self._frame, self._updated_at


class _CameraReader(threading.Thread):
    def __init__(self, *, rtsp_url: str, frame_buffer: _LatestFrameBuffer, camera_id: str) -> None:
        super().__init__(name=f"wp-stream-reader-{camera_id}", daemon=True)
        self._rtsp_url = rtsp_url
        self._frame_buffer = frame_buffer
        self._camera_id = camera_id
        self._stop = threading.Event()

    def run(self) -> None:
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("OpenCV is required for WatchPuppy stream server") from exc

        capture = None
        while not self._stop.is_set():
            if capture is None:
                capture = cv2.VideoCapture(self._rtsp_url)
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not capture.isOpened():
                    logger.warning(
                        "stream reader failed to open rtsp source",
                        extra={"camera_id": self._camera_id},
                    )
                    try:
                        capture.release()
                    except Exception:
                        pass
                    capture = None
                    time.sleep(2.0)
                    continue

            for _ in range(2):
                capture.grab()
            ok, image = capture.read()
            if not ok:
                logger.warning(
                    "stream reader failed to read frame",
                    extra={"camera_id": self._camera_id},
                )
                capture.release()
                capture = None
                time.sleep(1.0)
                continue

            ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if ok:
                self._frame_buffer.update(encoded.tobytes())
            time.sleep(0.08)

        if capture is not None:
            capture.release()

    def stop(self) -> None:
        self._stop.set()


class _MJPEGHandler(BaseHTTPRequestHandler):
    server: "_MJPEGServer"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/stream", "/stream.mjpg"}:
            self._serve_stream()
            return
        if parsed.path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _serve_stream(self) -> None:
        boundary = "watchpuppyframe"
        self.send_response(HTTPStatus.OK)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary}")
        self.end_headers()

        last_sent_at = 0.0
        while True:
            frame, updated_at = self.server.frame_buffer.snapshot()
            if frame is None:
                time.sleep(0.1)
                continue
            if updated_at <= last_sent_at:
                time.sleep(0.03)
                continue
            last_sent_at = updated_at
            try:
                self.wfile.write(f"--{boundary}\r\n".encode("ascii"))
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                break


class _MJPEGServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class, frame_buffer: _LatestFrameBuffer) -> None:
        super().__init__(server_address, handler_class)
        self.daemon_threads = True
        self.frame_buffer = frame_buffer


def _select_rtsp_url(config_path: Path, camera_id: str) -> str:
    with config_path.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}
    app_config_path = Path(raw.get("watchdog_config", config_path))
    settings = load_settings(app_config_path)
    for camera in settings.cameras:
        if camera.camera_id == camera_id or camera_id in camera.aliases:
            return camera.rtsp_url
    raise ValueError(f"camera_id not found in config: {camera_id}")


def run_mjpeg_server(*, config_path: Path, camera_id: str, host: str, port: int) -> None:
    rtsp_url = _select_rtsp_url(config_path, camera_id)
    frame_buffer = _LatestFrameBuffer()
    reader = _CameraReader(rtsp_url=rtsp_url, frame_buffer=frame_buffer, camera_id=camera_id)
    reader.start()
    server = _MJPEGServer((host, port), _MJPEGHandler, frame_buffer)
    logger.info(
        {
            "stream_server": "started",
            "camera_id": camera_id,
            "host": host,
            "port": port,
        }
    )
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        reader.stop()
        server.server_close()
