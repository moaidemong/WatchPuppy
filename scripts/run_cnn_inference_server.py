#!/usr/bin/env python3
from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchpuppy.inference.server import LoadedSnapshotModel
from watchpuppy.runtime.logging_runtime import configure_watchpuppy_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run WatchPuppy always-on CNN inference server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18021)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--image-size", type=int, required=True)
    parser.add_argument("--device", default="cpu")
    return parser


def main() -> None:
    configure_watchpuppy_logging()
    args = build_parser().parse_args()
    model = LoadedSnapshotModel(
        model_name=args.model_name,
        model_path=Path(args.model_path),
        image_size=args.image_size,
        device=args.device,
    )

    class Handler(BaseHTTPRequestHandler):
        server_version = "WatchPuppyCnn/1.0"

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"detail": "not found"})

        def do_POST(self) -> None:
            if self.path != "/infer":
                self._send_json(HTTPStatus.NOT_FOUND, {"detail": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            image_path = Path(str(payload["image_path"]))
            threshold = float(payload["threshold"])
            result = model.predict(image_path=image_path, threshold=threshold)
            self._send_json(HTTPStatus.OK, result)

        def log_message(self, format: str, *args) -> None:
            return

        def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
