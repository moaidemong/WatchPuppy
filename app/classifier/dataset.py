from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from app.core.schemas import EventFeatureVector


FEATURE_COLUMNS = [
    "event_id",
    "duration_s",
    "attempt_count",
    "body_lift_ratio",
    "progress_ratio",
    "pose_confidence_mean",
    "label",
]


@dataclass(slots=True)
class ReviewedDatasetRow:
    event_id: str
    duration_s: float
    attempt_count: int
    body_lift_ratio: float
    progress_ratio: float
    pose_confidence_mean: float
    predicted_label: str
    review_label: str
    review_status: str
    review_notes: str
    clip_path: str
    snapshot_path: str

    def feature_dict(self) -> dict[str, float]:
        return {
            "duration_s": self.duration_s,
            "attempt_count": float(self.attempt_count),
            "body_lift_ratio": self.body_lift_ratio,
            "progress_ratio": self.progress_ratio,
            "pose_confidence_mean": self.pose_confidence_mean,
        }


def append_labeled_feature_row(path: str | Path, features: EventFeatureVector, label: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    exists = file_path.exists()
    with file_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_COLUMNS)
        if not exists:
            writer.writeheader()
        row = features.to_dict() | {"label": label}
        writer.writerow(row)


def load_reviewed_training_rows(
    feature_dataset_path: str | Path,
    reviewed_labels_path: str | Path,
) -> list[ReviewedDatasetRow]:
    feature_rows = _read_feature_rows(feature_dataset_path)
    label_rows = _read_label_rows(reviewed_labels_path)

    reviewed_rows: list[ReviewedDatasetRow] = []
    for event_id, label_row in label_rows.items():
        feature_row = feature_rows.get(event_id)
        if feature_row is None:
            continue
        if label_row["review_status"] != "approved":
            continue
        reviewed_rows.append(
            ReviewedDatasetRow(
                event_id=event_id,
                duration_s=float(feature_row["duration_s"]),
                attempt_count=int(float(feature_row["attempt_count"])),
                body_lift_ratio=float(feature_row["body_lift_ratio"]),
                progress_ratio=float(feature_row["progress_ratio"]),
                pose_confidence_mean=float(feature_row["pose_confidence_mean"]),
                predicted_label=label_row["predicted_label"],
                review_label=label_row["review_label"],
                review_status=label_row["review_status"],
                review_notes=label_row["review_notes"],
                clip_path=label_row["clip_path"],
                snapshot_path=label_row["snapshot_path"],
            )
        )
    return reviewed_rows


def summarize_reviewed_training_rows(rows: list[ReviewedDatasetRow]) -> dict[str, object]:
    label_counts: dict[str, int] = {}
    for row in rows:
        label_counts[row.review_label] = label_counts.get(row.review_label, 0) + 1
    return {
        "row_count": len(rows),
        "label_counts": label_counts,
        "feature_columns": [
            "duration_s",
            "attempt_count",
            "body_lift_ratio",
            "progress_ratio",
            "pose_confidence_mean",
        ],
    }


def _read_feature_rows(path: str | Path) -> dict[str, dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8", newline="") as file_obj:
        return {
            row["event_id"]: row
            for row in csv.DictReader(file_obj)
            if row.get("event_id")
        }


def _read_label_rows(path: str | Path) -> dict[str, dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8", newline="") as file_obj:
        return {
            row["event_id"]: row
            for row in csv.DictReader(file_obj)
            if row.get("event_id")
        }
