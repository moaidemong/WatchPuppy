from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.schemas import BoundingBox, Detection
from app.detection.base import DogDetector
from app.ingest.frame_source import Frame

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenCVDnnDogDetectorConfig:
    model_path: str | None
    config_path: str | None
    labels_path: str | None
    dog_class_names: list[str]
    context_class_names: list[str]
    confidence_threshold: float
    input_width: int = 640
    input_height: int = 640
    scale_factor: float = 1.0 / 255.0
    swap_rb: bool = True


class OpenCVDnnDogDetector(DogDetector):
    """Adapter for OpenCV DNN models that emit dog detections."""

    def __init__(self, config: OpenCVDnnDogDetectorConfig) -> None:
        if not config.model_path:
            raise ValueError("model_path is required for opencv_dnn detector")
        if config.confidence_threshold <= 0:
            raise ValueError("confidence_threshold must be greater than zero")
        if config.input_width <= 0 or config.input_height <= 0:
            raise ValueError("input dimensions must be greater than zero")
        self.config = config
        self._labels = self._load_labels(config.labels_path)
        self._net = self._load_network(config)

    def _load_labels(self, labels_path: str | None) -> list[str]:
        if not labels_path:
            return []

        path = Path(labels_path)
        if not path.exists():
            raise ValueError(f"labels file does not exist: {labels_path}")

        return [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _load_network(self, config: OpenCVDnnDogDetectorConfig) -> Any:
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - depends on runtime environment
            raise RuntimeError(
                "OpenCV is required for the 'opencv_dnn' detector backend."
            ) from exc

        model_path = Path(config.model_path)
        if not model_path.exists():
            raise ValueError(f"detector model does not exist: {config.model_path}")

        if config.config_path:
            config_path = Path(config.config_path)
            if not config_path.exists():
                raise ValueError(f"detector config does not exist: {config.config_path}")
            return cv2.dnn.readNet(str(model_path), str(config_path))

        return cv2.dnn.readNet(str(model_path))

    def detect(self, frame: Frame) -> list[Detection]:
        image = frame.payload
        if image is None:
            return []
        if not hasattr(image, "shape"):
            raise ValueError("frame payload must be an image-like array for opencv_dnn detection")

        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - depends on runtime environment
            raise RuntimeError(
                "OpenCV is required for the 'opencv_dnn' detector backend."
            ) from exc

        image_height, image_width = image.shape[:2]
        blob = cv2.dnn.blobFromImage(
            image,
            scalefactor=self.config.scale_factor,
            size=(self.config.input_width, self.config.input_height),
            swapRB=self.config.swap_rb,
            crop=False,
        )
        self._net.setInput(blob)
        outputs = self._net.forward()
        detections = self._decode_outputs(outputs, image_width=image_width, image_height=image_height)
        logger.debug("decoded %s dog detections for frame=%s", len(detections), frame.index)
        return detections

    def detect_image(self, image: Any, *, frame_index: int = 0, timestamp_s: float = 0.0) -> list[Detection]:
        return self.detect(Frame(index=frame_index, timestamp_s=timestamp_s, payload=image))

    def _decode_outputs(self, outputs: Any, *, image_width: int, image_height: int) -> list[Detection]:
        rows = self._normalize_rows(outputs)
        detections: list[Detection] = []
        allowed_labels = set(self.config.dog_class_names) | set(self.config.context_class_names)

        for row in rows:
            if len(row) < 6:
                continue

            class_id = int(row[5])
            confidence = float(row[4])
            label = self._resolve_label(class_id)

            if label not in allowed_labels:
                continue
            if confidence < self.config.confidence_threshold:
                continue

            x1 = max(0.0, min(1.0, float(row[0]) / image_width))
            y1 = max(0.0, min(1.0, float(row[1]) / image_height))
            x2 = max(0.0, min(1.0, float(row[2]) / image_width))
            y2 = max(0.0, min(1.0, float(row[3]) / image_height))

            detections.append(
                Detection(
                    label=label,
                    confidence=confidence,
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                )
            )

        return detections

    def _resolve_label(self, class_id: int) -> str:
        if 0 <= class_id < len(self._labels):
            return self._labels[class_id]
        return str(class_id)

    def _normalize_rows(self, outputs: Any) -> list[list[float]]:
        if hasattr(outputs, "tolist"):
            outputs = outputs.tolist()

        if not isinstance(outputs, list):
            return []

        if outputs and isinstance(outputs[0], list) and outputs[0] and isinstance(outputs[0][0], list):
            flattened: list[list[float]] = []
            for block in outputs:
                for row in block:
                    if isinstance(row, list):
                        flattened.append(row)
            return flattened

        return [row for row in outputs if isinstance(row, list)]
