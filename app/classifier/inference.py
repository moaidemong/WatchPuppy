from __future__ import annotations

from typing import Any


TARGET_CLASSIFIER_LABELS = {"failed_get_up_attempt", "slump_or_collapse"}


def build_detection_context(
    *,
    dog_labels: set[str],
    detections_by_frame: list[list[dict[str, Any]]],
) -> dict[str, object]:
    non_dog_labels: set[str] = set()
    total_non_dog_detections = 0
    for frame_detections in detections_by_frame:
        for detection in frame_detections:
            label = str(detection.get("label", ""))
            if not label or label in dog_labels:
                continue
            non_dog_labels.add(label)
            total_non_dog_detections += 1
    return {
        "non_dog_labels": sorted(non_dog_labels),
        "has_person": "person" in non_dog_labels,
        "has_cat": "cat" in non_dog_labels,
        "has_non_dog_context": bool(non_dog_labels),
        "total_non_dog_detections": total_non_dog_detections,
    }


def apply_context_penalty(
    raw_label: str,
    raw_score: float,
    *,
    detection_context: dict[str, object],
) -> tuple[str, float, list[str], float]:
    penalty_factor = 1.0
    penalty_reasons: list[str] = []
    if detection_context.get("has_person"):
        penalty_factor *= 0.6
        penalty_reasons.append("person detected in event")
    if detection_context.get("has_cat"):
        penalty_factor *= 0.7
        penalty_reasons.append("cat detected in event")
    non_dog_labels = [
        str(label)
        for label in detection_context.get("non_dog_labels", [])
        if str(label) not in {"person", "cat"}
    ]
    if non_dog_labels:
        penalty_factor *= 0.8
        penalty_reasons.append("other object context detected")

    adjusted_score = round(raw_score * penalty_factor, 4)
    adjusted_label = raw_label
    if raw_label in TARGET_CLASSIFIER_LABELS and penalty_factor < 1.0 and adjusted_score < 0.45:
        adjusted_label = "non_target"
    return adjusted_label, adjusted_score, penalty_reasons, round(penalty_factor, 4)
