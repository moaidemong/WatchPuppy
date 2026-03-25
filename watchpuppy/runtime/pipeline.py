from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from watchpuppy.runtime.config import WatchPuppySettings
from watchpuppy.runtime.review_queue import write_review_queue_item
from watchpuppy.runtime.watchdog_bridge import run_watchdog_capture_once
from watchpuppy.upstream.yolo_shrink import YoloShrinkConfig, _build_detector, shrink_single_snapshot


@dataclass(slots=True)
class WatchPuppyRuntime:
    settings: WatchPuppySettings
    epoch: str
    detector = None

    def __post_init__(self) -> None:
        self.detector = _build_detector(
            YoloShrinkConfig(
                input_manifest_path=self.settings.storage.exports_dir / "_unused.csv",
                output_root=self.settings.storage.shrink_dir,
                report_path=self.settings.storage.exports_dir / "yolo_shrink_runtime_report.csv",
                margin_ratio=self.settings.runtime.margin_ratio,
            )
        )

    def close(self) -> None:
        if self.detector is not None:
            self.detector.close()
            self.detector = None

    def run_capture_and_infer(self, camera_id: str) -> list[Path]:
        metadata_paths = run_watchdog_capture_once(
            watchdog_root=self.settings.watchdog_root,
            watchdog_config=self.settings.watchdog_config,
            camera_id=camera_id,
            artifacts_dir=self.settings.storage.artifacts_dir,
            review_queue_dir=self.settings.storage.review_queue_dir,
            exports_dir=self.settings.storage.exports_dir,
        )
        for metadata_path in metadata_paths:
            self._post_process_metadata(metadata_path)
        return metadata_paths

    def _post_process_metadata(self, metadata_path: Path) -> None:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        event = payload.get("event", {}) or {}
        media = payload.get("media", {}) or {}
        event_id = str(event.get("event_id", ""))
        camera_id = str(event.get("camera_id", event_id.split("-", 1)[0] if event_id else ""))
        snapshot_path = Path(str(media.get("snapshot_path", "")))
        clip_path = Path(str(media.get("clip_path", ""))) if media.get("clip_path") else None
        if not event_id or not snapshot_path.exists():
            return

        shrink_path = snapshot_path.parent / "snapshot_shrink.jpg"
        shrink_result = shrink_single_snapshot(
            self.detector,
            input_path=snapshot_path,
            output_path=shrink_path,
            dog_class_names=("dog", "horse"),
            margin_ratio=self.settings.runtime.margin_ratio,
        )
        blocked_labels = [
            label
            for label in shrink_result.context_labels
            if label in set(self.settings.runtime.block_on_context_labels)
        ]

        if blocked_labels:
            prediction = {
                "label": "non_target",
                "score": 0.0,
                "threshold": self.settings.runtime.threshold,
                "reason": f"context_blocked:{','.join(blocked_labels)}",
            }
        elif shrink_result.status != "cropped":
            prediction = {
                "label": "non_target",
                "score": 0.0,
                "threshold": self.settings.runtime.threshold,
                "reason": shrink_result.status,
            }
        else:
            prediction = self._run_cnn_inference(shrink_path)
            prediction["reason"] = "cnn"

        payload["watchpuppy"] = {
            "epoch": self.epoch,
            "shrink_path": str(shrink_path),
            "shrink_status": shrink_result.status,
            "context_labels": list(shrink_result.context_labels),
            "blocked_context_labels": blocked_labels,
            "cnn_prediction": prediction,
        }
        metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        queue_item = {
            "event_id": event_id,
            "camera_id": camera_id,
            "epoch": self.epoch,
            "captured_at": str(payload.get("captured_at", "")),
            "predicted_label": prediction["label"],
            "classifier_label": prediction["label"],
            "classifier_score": float(prediction["score"]),
            "clip_path": str(clip_path.relative_to(self.settings.storage.artifacts_dir.parent)) if clip_path else "",
            "snapshot_path": str(snapshot_path.relative_to(self.settings.storage.artifacts_dir.parent)),
            "metadata_path": str(metadata_path.relative_to(self.settings.storage.artifacts_dir.parent)),
            "review_status": "pending",
            "review_label": "",
            "review_notes": prediction["reason"],
            "version": 1,
        }
        write_review_queue_item(self.settings.storage.review_queue_dir / f"{event_id}.json", queue_item)

    def _run_cnn_inference(self, image_path: Path) -> dict[str, Any]:
        command = [
            "/home/moai/Workspace/Codex/WatchPuppy/.venv/bin/python",
            str(Path(__file__).resolve().parents[2] / "scripts" / "infer_snapshot.py"),
            "--model-name",
            self.settings.runtime.model_name,
            "--model-path",
            str(self.settings.runtime.model_path),
            "--image-path",
            str(image_path),
            "--image-size",
            str(self.settings.runtime.image_size),
            "--threshold",
            str(self.settings.runtime.threshold),
            "--device",
            "cpu",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
