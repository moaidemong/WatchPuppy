from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.schemas import BoundingBox, Detection
from app.detection.base import DogDetector
from app.ingest.frame_source import Frame


@dataclass(slots=True)
class HailoHefDogDetectorConfig:
    model_path: str | None
    labels_path: str | None
    dog_class_names: list[str]
    context_class_names: list[str]
    confidence_threshold: float
    input_width: int = 640
    input_height: int = 640
    stream_interface: str = "PCIe"


class HailoHefDogDetector(DogDetector):
    """Hailo HEF detector with YOLO NMS output decoding."""

    def __init__(self, config: HailoHefDogDetectorConfig) -> None:
        if not config.model_path:
            raise ValueError("model_path is required for hailo_hef detector")
        self.config = config
        self._labels = self._load_labels(config.labels_path)
        self._hef = None
        self._infer_pipeline = None
        self._input_name = None
        self._activation_context = None

    def detect(self, frame: Frame) -> list[Detection]:
        image = frame.payload
        if image is None:
            return []
        if not hasattr(image, "shape"):
            raise ValueError("frame payload must be an image-like array for hailo_hef detection")
        self._ensure_initialized()
        prepared = self._prepare_image(image)
        result = self._infer_pipeline.infer({self._input_name: prepared})
        output_name, output_tensor = next(iter(result.items()))
        return self._decode_nms_tensor(output_name, output_tensor, image.shape[1], image.shape[0])

    def detect_image(self, image: Any, *, frame_index: int = 0, timestamp_s: float = 0.0) -> list[Detection]:
        return self.detect(Frame(index=frame_index, timestamp_s=timestamp_s, payload=image))

    def debug_image(self, image: Any) -> dict[str, Any]:
        self._ensure_initialized()
        prepared = self._prepare_image(image)
        result = self._infer_pipeline.infer({self._input_name: prepared})
        output_name, output_tensor = next(iter(result.items()))
        class_boxes = self._iter_class_boxes(output_name, output_tensor)
        class_summaries = []
        for class_id, boxes in enumerate(class_boxes):
            label = self._resolve_label(class_id)
            scores = [float(row[4]) for row in boxes if len(row) >= 5]
            if not scores:
                continue
            class_summaries.append(
                {
                    "class_id": class_id,
                    "label": label,
                    "count": len(scores),
                    "max_score": round(max(scores), 6),
                }
            )
        class_summaries.sort(key=lambda item: item["max_score"], reverse=True)
        dog_entries = [item for item in class_summaries if item["label"] in self.config.dog_class_names]
        return {
            "output_name": output_name,
            "top_classes": class_summaries[:10],
            "dog_entries": dog_entries[:10],
        }

    def close(self) -> None:
        infer_pipeline = self._infer_pipeline
        self._infer_pipeline = None
        if infer_pipeline is not None:
            infer_pipeline.__exit__(None, None, None)
        activation_context = self._activation_context
        self._activation_context = None
        if activation_context is not None:
            activation_context.__exit__(None, None, None)

    def _ensure_initialized(self) -> None:
        if self._infer_pipeline is not None:
            return

        try:
            import numpy as np  # noqa: F401
            from hailo_platform import (
                ConfigureParams,
                HEF,
                HailoStreamInterface,
                InferVStreams,
                InputVStreamParams,
                OutputVStreamParams,
                VDevice,
            )
        except ImportError as exc:  # pragma: no cover - runtime dependent
            raise RuntimeError(
                "hailo_platform is required for the 'hailo_hef' detector backend."
            ) from exc

        model_path = Path(self.config.model_path)
        if not model_path.exists():
            raise ValueError(f"Hailo HEF model does not exist: {self.config.model_path}")

        self._hef = HEF(str(model_path))
        interface = getattr(HailoStreamInterface, self.config.stream_interface)
        try:
            self._vdevice = VDevice()
            configure_params = ConfigureParams.create_from_hef(self._hef, interface=interface)
            network_groups = self._vdevice.configure(self._hef, configure_params)
        except Exception as exc:  # pragma: no cover - runtime dependent
            raise RuntimeError(
                "Failed to open Hailo device for inference. "
                "Check /dev/hailo0, driver state, and hailort service."
            ) from exc
        network_group = network_groups[0]
        self._activation_context = network_group.activate()
        self._activation_context.__enter__()
        input_params = InputVStreamParams.make_from_network_group(network_group)
        output_params = OutputVStreamParams.make_from_network_group(network_group)
        infer_pipeline = InferVStreams(network_group, input_params, output_params)
        self._infer_pipeline = infer_pipeline.__enter__()
        self._input_name = self._hef.get_input_vstream_infos()[0].name

    def _load_labels(self, labels_path: str | None) -> list[str]:
        if not labels_path:
            return []
        path = Path(labels_path)
        if not path.exists():
            raise ValueError(f"labels file does not exist: {labels_path}")
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _prepare_image(self, image: Any) -> Any:
        try:
            import cv2
            import numpy as np
        except ImportError as exc:  # pragma: no cover - runtime dependent
            raise RuntimeError("OpenCV and numpy are required for hailo_hef detection.") from exc

        resized = cv2.resize(image, (self.config.input_width, self.config.input_height))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        if rgb.dtype != np.uint8:
            rgb = rgb.astype(np.uint8)
        return rgb[None, ...]

    def _decode_nms_tensor(
        self,
        output_name: str,
        output_tensor: Any,
        image_width: int,
        image_height: int,
    ) -> list[Detection]:
        detections: list[Detection] = []
        allowed_labels = set(self.config.dog_class_names) | set(self.config.context_class_names)
        for class_id, class_boxes in enumerate(self._iter_class_boxes(output_name, output_tensor)):
            label = self._resolve_label(class_id)
            if label not in allowed_labels:
                continue

            for row in class_boxes:
                if len(row) < 5:
                    continue
                score = float(row[4])
                if score < self.config.confidence_threshold:
                    continue
                y1, x1, y2, x2 = [float(value) for value in row[:4]]
                x1, x2 = self._normalize_axis(x1, x2, image_width)
                y1, y2 = self._normalize_axis(y1, y2, image_height)
                detections.append(
                    Detection(
                        label=label,
                        confidence=score,
                        bbox=BoundingBox(
                            x1=x1,
                            y1=y1,
                            x2=x2,
                            y2=y2,
                        ),
                    )
                )
        return detections

    def _iter_class_boxes(self, output_name: str, output_tensor: Any) -> list[list[list[float]]]:
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("numpy is required for hailo_hef detection decoding.") from exc

        tensor = output_tensor

        if isinstance(tensor, list) and len(tensor) == 1:
            tensor = tensor[0]

        if isinstance(tensor, tuple):
            tensor = list(tensor)

        if isinstance(tensor, list):
            normalized: list[list[list[float]]] = []
            for class_boxes in tensor:
                if hasattr(class_boxes, "tolist"):
                    class_boxes = class_boxes.tolist()
                if not isinstance(class_boxes, list):
                    normalized.append([])
                    continue
                while (
                    len(class_boxes) == 1
                    and isinstance(class_boxes[0], list)
                    and class_boxes[0]
                    and isinstance(class_boxes[0][0], list)
                ):
                    class_boxes = class_boxes[0]
                if class_boxes and not isinstance(class_boxes[0], list):
                    normalized.append([class_boxes])
                else:
                    normalized.append(class_boxes)
            return normalized

        array = np.asarray(tensor)
        if array.ndim == 4 and array.shape[0] == 1:
            array = array[0]
        if array.ndim != 3:
            raise ValueError(f"unexpected Hailo NMS tensor shape for {output_name}: {array.shape}")

        if array.shape[1] == 5:
            array = np.transpose(array, (0, 2, 1))
        elif array.shape[2] != 5:
            raise ValueError(f"unexpected Hailo NMS tensor layout for {output_name}: {array.shape}")

        return array.tolist()

    def _resolve_label(self, class_id: int) -> str:
        if 0 <= class_id < len(self._labels):
            return self._labels[class_id]
        return str(class_id)

    def _normalize_axis(self, start: float, end: float, size: int) -> tuple[float, float]:
        if max(abs(start), abs(end)) <= 1.5:
            return (
                max(0.0, min(1.0, start)),
                max(0.0, min(1.0, end)),
            )
        return (
            max(0.0, min(1.0, start / size)),
            max(0.0, min(1.0, end / size)),
        )
