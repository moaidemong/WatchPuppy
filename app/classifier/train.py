from __future__ import annotations

from pathlib import Path

from app.classifier.dataset import load_reviewed_training_rows, summarize_reviewed_training_rows
from app.classifier.model import FEATURE_NAMES, Prototype, PrototypeModel


TARGET_LABELS_V1 = {"failed_get_up_attempt", "slump_or_collapse"}
TARGET_LABELS_V2 = {"failed_get_up_attempt", "restless_while_lying"}


def train_classifier(
    feature_dataset_path: str | Path,
    reviewed_labels_path: str | Path,
    *,
    min_samples_per_label: int = 1,
    label_scheme: str = "original",
) -> dict[str, object]:
    rows = load_reviewed_training_rows(feature_dataset_path, reviewed_labels_path)
    summary = summarize_reviewed_training_rows(rows)
    mapped_rows = _apply_label_scheme(rows, label_scheme=label_scheme)
    mapped_summary = summarize_reviewed_training_rows(mapped_rows)
    label_counts = dict(summary["label_counts"])
    mapped_label_counts = dict(mapped_summary["label_counts"])
    included_labels = sorted(
        [label for label, count in mapped_label_counts.items() if count >= min_samples_per_label]
    )
    excluded_labels = {
        label: count for label, count in mapped_label_counts.items() if count < min_samples_per_label
    }
    filtered_rows = [row for row in mapped_rows if row.review_label in set(included_labels)]
    prototypes = _build_prototypes(filtered_rows)
    summary["model"] = PrototypeModel(
        model_type="nearest_prototype",
        feature_names=FEATURE_NAMES.copy(),
        prototypes=prototypes,
    )
    summary["label_scheme"] = label_scheme
    summary["raw_label_counts"] = label_counts
    summary["label_counts"] = mapped_label_counts
    summary["min_samples_per_label"] = min_samples_per_label
    summary["included_labels"] = included_labels
    summary["excluded_labels"] = excluded_labels
    summary["training_row_count"] = len(filtered_rows)
    return summary


def _build_prototypes(rows) -> list[Prototype]:
    grouped: dict[str, list[dict[str, float]]] = {}
    for row in rows:
        grouped.setdefault(row.review_label, []).append(row.feature_dict())

    prototypes: list[Prototype] = []
    for label, feature_rows in grouped.items():
        center = {
            feature_name: sum(row[feature_name] for row in feature_rows) / len(feature_rows)
            for feature_name in FEATURE_NAMES
        }
        prototypes.append(
            Prototype(
                label=label,
                center={name: round(value, 6) for name, value in center.items()},
                sample_count=len(feature_rows),
            )
        )
    prototypes.sort(key=lambda item: item.label)
    return prototypes


def _apply_label_scheme(rows, *, label_scheme: str):
    if label_scheme == "original":
        return rows
    target_labels: set[str] | None = None
    if label_scheme == "target_focus_v1":
        target_labels = TARGET_LABELS_V1
    elif label_scheme == "target_focus_v2":
        target_labels = TARGET_LABELS_V2

    if target_labels is not None:
        mapped_rows = []
        for row in rows:
            mapped_label = row.review_label if row.review_label in target_labels else "non_target"
            mapped_rows.append(
                row.__class__(
                    event_id=row.event_id,
                    duration_s=row.duration_s,
                    attempt_count=row.attempt_count,
                    body_lift_ratio=row.body_lift_ratio,
                    progress_ratio=row.progress_ratio,
                    pose_confidence_mean=row.pose_confidence_mean,
                    predicted_label=row.predicted_label,
                    review_label=mapped_label,
                    review_status=row.review_status,
                    review_notes=row.review_notes,
                    clip_path=row.clip_path,
                    snapshot_path=row.snapshot_path,
                )
            )
        return mapped_rows
    raise ValueError(f"unsupported label_scheme: {label_scheme}")
