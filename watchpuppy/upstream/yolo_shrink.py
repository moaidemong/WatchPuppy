from __future__ import annotations

import csv
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.detection.hailo_hef_detector import HailoHefDogDetector, HailoHefDogDetectorConfig  # noqa: E402


logger = logging.getLogger("watchpuppy.front_yolo_process")


@dataclass(frozen=True)
class YoloShrinkConfig:
    input_manifest_path: Path
    output_root: Path
    report_path: Path
    model_path: Path = Path("/usr/share/hailo-models/yolov8s_h8.hef")
    labels_path: Path = PROJECT_ROOT / "configs" / "dog_labels.coco.txt"
    confidence_threshold: float = 0.20
    margin_ratio: float = 0.20
    dog_class_names: tuple[str, ...] = ("dog", "horse")
    context_class_names: tuple[str, ...] = ("person", "cat")


@dataclass(frozen=True)
class ShrinkResult:
    event_id: str
    epoch: str
    input_path: str
    output_path: str
    status: str
    detection_label: str
    detection_confidence: float
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class SingleShrinkResult:
    input_path: str
    output_path: str
    status: str
    detection_label: str
    detection_confidence: float
    context_labels: tuple[str, ...]
    x1: int
    y1: int
    x2: int
    y2: int


def _build_detector(config: YoloShrinkConfig) -> HailoHefDogDetector:
    return HailoHefDogDetector(
        HailoHefDogDetectorConfig(
            model_path=str(config.model_path),
            labels_path=str(config.labels_path),
            dog_class_names=list(config.dog_class_names),
            context_class_names=list(config.context_class_names),
            confidence_threshold=config.confidence_threshold,
            input_width=640,
            input_height=640,
            stream_interface="PCIe",
        )
    )


def _iter_manifest_rows(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def _pick_best_dog_detection(detections: list[object], dog_labels: set[str]) -> object | None:
    dog_detections = [det for det in detections if getattr(det, "label", None) in dog_labels]
    if not dog_detections:
        return None
    return max(dog_detections, key=lambda det: float(getattr(det, "confidence", 0.0)))


def _crop_bounds(detection: object, width: int, height: int, margin_ratio: float) -> tuple[int, int, int, int]:
    bbox = getattr(detection, "bbox")
    x1 = int(round(float(getattr(bbox, "x1")) * width))
    y1 = int(round(float(getattr(bbox, "y1")) * height))
    x2 = int(round(float(getattr(bbox, "x2")) * width))
    y2 = int(round(float(getattr(bbox, "y2")) * height))

    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)
    margin_x = int(round(box_w * margin_ratio))
    margin_y = int(round(box_h * margin_ratio))

    x1 = max(0, x1 - margin_x)
    y1 = max(0, y1 - margin_y)
    x2 = min(width, x2 + margin_x)
    y2 = min(height, y2 + margin_y)
    return x1, y1, x2, y2


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def shrink_single_snapshot(
    detector: HailoHefDogDetector,
    *,
    input_path: Path,
    output_path: Path,
    dog_class_names: tuple[str, ...],
    margin_ratio: float,
) -> SingleShrinkResult:
    import cv2

    _ensure_parent(output_path)
    image = cv2.imread(str(input_path))
    if image is None:
        raise ValueError(f"failed to read image: {input_path}")
    height, width = image.shape[:2]
    detections = detector.detect_image(image)
    logger.debug(
        json.dumps(
            {
                "phase": "detect",
                "input_path": str(input_path),
                "detection_count": len(detections),
            },
            ensure_ascii=False,
        )
    )
    context_labels = tuple(
        sorted(
            {
                str(getattr(det, "label", ""))
                for det in detections
                if str(getattr(det, "label", "")) and str(getattr(det, "label", "")) not in set(dog_class_names)
            }
        )
    )
    best = _pick_best_dog_detection(detections, set(dog_class_names))
    if best is None:
        cv2.imwrite(str(output_path), image)
        logger.info(
            json.dumps(
                {
                    "phase": "fallback",
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "status": "fallback_original",
                    "context_labels": context_labels,
                },
                ensure_ascii=False,
            )
        )
        return SingleShrinkResult(
            input_path=str(input_path),
            output_path=str(output_path),
            status="fallback_original",
            detection_label="",
            detection_confidence=0.0,
            context_labels=context_labels,
            x1=0,
            y1=0,
            x2=width,
            y2=height,
        )

    x1, y1, x2, y2 = _crop_bounds(best, width, height, margin_ratio)
    cropped = image[y1:y2, x1:x2]
    if cropped.size == 0:
        cv2.imwrite(str(output_path), image)
        logger.info(
            json.dumps(
                {
                    "phase": "fallback",
                    "input_path": str(input_path),
                    "output_path": str(output_path),
                    "status": "fallback_empty_crop",
                    "context_labels": context_labels,
                },
                ensure_ascii=False,
            )
        )
        return SingleShrinkResult(
            input_path=str(input_path),
            output_path=str(output_path),
            status="fallback_empty_crop",
            detection_label=str(getattr(best, "label", "")),
            detection_confidence=float(getattr(best, "confidence", 0.0)),
            context_labels=context_labels,
            x1=0,
            y1=0,
            x2=width,
            y2=height,
        )

    cv2.imwrite(str(output_path), cropped)
    logger.info(
        json.dumps(
            {
                "phase": "cropped",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "label": str(getattr(best, "label", "")),
                "confidence": float(getattr(best, "confidence", 0.0)),
                "context_labels": context_labels,
                "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            },
            ensure_ascii=False,
        )
    )
    return SingleShrinkResult(
        input_path=str(input_path),
        output_path=str(output_path),
        status="cropped",
        detection_label=str(getattr(best, "label", "")),
        detection_confidence=float(getattr(best, "confidence", 0.0)),
        context_labels=context_labels,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
    )


def write_yolo_shrink_snapshots(config: YoloShrinkConfig) -> dict[str, int]:
    import cv2

    rows = _iter_manifest_rows(config.input_manifest_path)
    detector = _build_detector(config)
    results: list[ShrinkResult] = []
    crop_count = 0
    fallback_count = 0
    try:
        for row in rows:
            event_id = row["event_id"]
            epoch = row["epoch"]
            image_path = Path(row["snapshot_path"])
            if not image_path.is_absolute():
                image_path = config.input_manifest_path.parents[1] / image_path

            output_path = config.output_root / epoch / f"{event_id}.jpg"
            _ensure_parent(output_path)

            single = shrink_single_snapshot(
                detector,
                input_path=image_path,
                output_path=output_path,
                dog_class_names=config.dog_class_names,
                margin_ratio=config.margin_ratio,
            )
            results.append(
                ShrinkResult(
                    event_id=event_id,
                    epoch=epoch,
                    input_path=single.input_path,
                    output_path=single.output_path,
                    status=single.status,
                    detection_label=single.detection_label,
                    detection_confidence=single.detection_confidence,
                    x1=single.x1,
                    y1=single.y1,
                    x2=single.x2,
                    y2=single.y2,
                )
            )
            if single.status == "cropped":
                crop_count += 1
            else:
                fallback_count += 1
    finally:
        detector.close()

    _ensure_parent(config.report_path)
    with config.report_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "event_id",
                "epoch",
                "input_path",
                "output_path",
                "status",
                "detection_label",
                "detection_confidence",
                "x1",
                "y1",
                "x2",
                "y2",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "event_id": result.event_id,
                    "epoch": result.epoch,
                    "input_path": result.input_path,
                    "output_path": result.output_path,
                    "status": result.status,
                    "detection_label": result.detection_label,
                    "detection_confidence": f"{result.detection_confidence:.6f}",
                    "x1": result.x1,
                    "y1": result.y1,
                    "x2": result.x2,
                    "y2": result.y2,
                }
            )

    return {
        "total": len(results),
        "cropped": crop_count,
        "fallback": fallback_count,
    }
