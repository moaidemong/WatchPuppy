from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request

from watchpuppy.runtime.config import WatchPuppySettings
from watchpuppy.runtime.logging_runtime import current_transaction_id, transaction_logging
from watchpuppy.runtime.notifier import send_failed_get_up_alert_async
from watchpuppy.runtime.picmosaic_meta import append_picmosaic_index_online
from watchpuppy.runtime.review_queue import write_review_queue_item
from watchpuppy.runtime.watchdog_bridge import run_watchdog_capture_once
from watchpuppy.upstream.yolo_shrink import YoloShrinkConfig, _build_detector, shrink_single_snapshot

logger = logging.getLogger("watchpuppy.backbone")
front_logger = logging.getLogger("watchpuppy.front_yolo_process")
backend_logger = logging.getLogger("watchpuppy.backend_cnn_process")


@dataclass(slots=True)
class WatchPuppyRuntime:
    settings: WatchPuppySettings
    epoch: str
    detector: Any | None = None

    def close(self) -> None:
        if self.detector is not None:
            self.detector.close()
            self.detector = None

    def run_capture_and_infer(self, camera_id: str, transaction_id: str | None = None) -> list[Path]:
        with transaction_logging(transaction_id or current_transaction_id()):
            metadata_paths = run_watchdog_capture_once(
                watchdog_root=self.settings.watchdog_root,
                watchdog_config=self.settings.watchdog_config,
                camera_id=camera_id,
                epoch=self.epoch,
                transaction_id=current_transaction_id(),
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
        detector = self._get_detector()
        try:
            shrink_result = shrink_single_snapshot(
                detector,
                input_path=snapshot_path,
                output_path=shrink_path,
                dog_class_names=tuple(self.settings.runtime.allowed_detection_labels),
                margin_ratio=self.settings.runtime.margin_ratio,
            )
        finally:
            self.close()
        detection_label_allowed = shrink_result.detection_label in set(self.settings.runtime.allowed_detection_labels)
        front_logger.info(
            json.dumps(
                {
                    "camera_id": camera_id,
                    "event_id": event_id,
                    "input_path": str(snapshot_path),
                    "output_path": str(shrink_path),
                    "status": shrink_result.status,
                    "detection_label_allowed": detection_label_allowed,
                    "context_labels": list(shrink_result.context_labels),
                    "bbox": {
                        "x1": shrink_result.x1,
                        "y1": shrink_result.y1,
                        "x2": shrink_result.x2,
                        "y2": shrink_result.y2,
                    },
                    "detection_label": shrink_result.detection_label,
                    "detection_confidence": float(shrink_result.detection_confidence),
                },
                ensure_ascii=False,
            )
        )
        blocked_labels = [
            label
            for label in shrink_result.context_labels
            if label in set(self.settings.runtime.block_on_context_labels)
        ]

        if not detection_label_allowed:
            prediction = {
                "label": "non_target",
                "score": 0.0,
                "threshold": self.settings.runtime.threshold,
                "reason": f"detection_label_filtered:{shrink_result.detection_label or 'none'}",
            }
        elif blocked_labels:
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

        notification: dict[str, Any] | None = None
        if prediction["label"] == "failed_get_up_attempt":
            notification = send_failed_get_up_alert_async(
                event_id=event_id,
                camera_id=camera_id,
                epoch=self.epoch,
                score=float(prediction["score"]),
                threshold=float(prediction["threshold"]),
                snapshot_path=snapshot_path,
                transaction_id=current_transaction_id(),
            )

        payload["watchpuppy"] = {
            "epoch": self.epoch,
            "transaction_id": current_transaction_id(),
            "shrink_path": str(shrink_path),
            "shrink_status": shrink_result.status,
            "detection_label_allowed": detection_label_allowed,
            "context_labels": list(shrink_result.context_labels),
            "blocked_context_labels": blocked_labels,
            "cnn_prediction": prediction,
            "notification": notification,
        }
        metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        picmosaic_record = append_picmosaic_index_online(
            artifacts_root=self.settings.storage.artifacts_dir,
            metadata_path=metadata_path,
            payload=payload,
        )

        queue_item = {
            "event_id": event_id,
            "camera_id": camera_id,
            "epoch": self.epoch,
            "transaction_id": current_transaction_id(),
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
        logger.info(
            json.dumps(
                {
                    "camera_id": camera_id,
                    "event_id": event_id,
                    "transaction_id": current_transaction_id(),
                    "epoch": self.epoch,
                    "snapshot_path": str(snapshot_path),
                    "shrink_path": str(shrink_path),
                    "shrink_status": shrink_result.status,
                    "detection_label_allowed": detection_label_allowed,
                    "context_labels": list(shrink_result.context_labels),
                    "blocked_context_labels": blocked_labels,
                    "classifier_label": prediction["label"],
                    "classifier_score": float(prediction["score"]),
                    "threshold": float(prediction["threshold"]),
                    "notification": notification,
                    "picmosaic_appended": bool(picmosaic_record),
                },
                ensure_ascii=False,
            )
        )

    def _run_cnn_inference(self, image_path: Path) -> dict[str, Any]:
        infer_url = f"{self.settings.runtime.server_url}/infer"
        payload = json.dumps(
            {
                "image_path": str(image_path),
                "threshold": self.settings.runtime.threshold,
            }
        ).encode("utf-8")
        backend_logger.info(
            json.dumps(
                {
                    "image_path": str(image_path),
                    "model_name": self.settings.runtime.model_name,
                    "model_path": str(self.settings.runtime.model_path),
                    "image_size": self.settings.runtime.image_size,
                    "threshold": self.settings.runtime.threshold,
                    "server_url": self.settings.runtime.server_url,
                    "phase": "start",
                },
                ensure_ascii=False,
            )
        )
        req = request.Request(
            infer_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=10) as response:
            prediction = json.loads(response.read().decode("utf-8"))
        backend_logger.info(
            json.dumps(
                {
                    "image_path": str(image_path),
                    "phase": "done",
                    "prediction": prediction,
                },
                ensure_ascii=False,
            )
        )
        return prediction

    def _get_detector(self) -> Any:
        if self.detector is None:
            self.detector = _build_detector(
                YoloShrinkConfig(
                    input_manifest_path=self.settings.storage.exports_dir / "_unused.csv",
                    output_root=self.settings.storage.shrink_dir,
                    report_path=self.settings.storage.exports_dir / "yolo_shrink_runtime_report.csv",
                    margin_ratio=self.settings.runtime.margin_ratio,
                )
            )
        return self.detector
