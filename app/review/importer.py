from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from app.core.config import StorageSettings
from app.storage.local_store import JsonFileStore


LABEL_COLUMNS = [
    "event_id",
    "captured_at",
    "start_s",
    "end_s",
    "duration_s",
    "predicted_label",
    "review_label",
    "review_status",
    "review_notes",
    "clip_path",
    "snapshot_path",
]


def _normalize_review_notes(value: str | None) -> str:
    text = str(value or "")
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n")]
    return " ".join(line for line in lines if line).strip()


@dataclass(slots=True)
class ReviewImportResult:
    manifest_path: Path
    labels_path: Path
    imported_count: int


class ReviewLabelImporter:
    def __init__(self, storage: StorageSettings, store: JsonFileStore | None = None) -> None:
        self.storage = storage
        self.store = store or JsonFileStore()

    def import_manifest(self, manifest_path: str | Path) -> ReviewImportResult:
        path = Path(manifest_path)
        rows = self._read_rows(path)
        approved_rows = [row for row in rows if row.get("review_status") in {"approved", "rejected"}]
        labels_path = self.storage.exports_dir / "labels" / "clips.csv"
        self._append_labels(labels_path, approved_rows)
        for row in approved_rows:
            self._write_review_back(row)
        return ReviewImportResult(
            manifest_path=path,
            labels_path=labels_path,
            imported_count=len(approved_rows),
        )

    def _read_rows(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as file_obj:
            return list(csv.DictReader(file_obj))

    def _append_labels(self, labels_path: Path, rows: list[dict[str, str]]) -> None:
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        existing_rows: dict[str, dict[str, str]] = {}
        if labels_path.exists():
            with labels_path.open("r", encoding="utf-8", newline="") as file_obj:
                existing_rows = {
                    row["event_id"]: row
                    for row in csv.DictReader(file_obj)
                    if row.get("event_id")
                }

        for row in rows:
            event_id = row.get("event_id", "")
            if not event_id:
                continue
            existing_rows[event_id] = {
                "event_id": event_id,
                "captured_at": row.get("captured_at", ""),
                "start_s": row.get("start_s", ""),
                "end_s": row.get("end_s", ""),
                "duration_s": row.get("duration_s", ""),
                "predicted_label": row.get("predicted_label", ""),
                "review_label": row.get("review_label", ""),
                "review_status": row.get("review_status", ""),
                "review_notes": _normalize_review_notes(row.get("review_notes", "")),
                "clip_path": row.get("clip_path", ""),
                "snapshot_path": row.get("snapshot_path", ""),
            }

        with labels_path.open("w", encoding="utf-8", newline="") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=LABEL_COLUMNS)
            writer.writeheader()
            for event_id in sorted(existing_rows):
                writer.writerow(existing_rows[event_id])

    def _write_review_back(self, row: dict[str, str]) -> None:
        event_id = row.get("event_id")
        if not event_id:
            return

        review_payload = {
            "status": row.get("review_status", ""),
            "label": row.get("review_label", ""),
            "notes": _normalize_review_notes(row.get("review_notes", "")),
        }

        queue_path = self.storage.review_queue_dir / f"{event_id}.json"
        if queue_path.exists():
            payload = self.store.read(queue_path)
            payload["review"] = review_payload
            self.store.write(queue_path, payload)

        metadata_dir = row.get("metadata_path")
        if metadata_dir:
            metadata_path = Path(metadata_dir) / "metadata.json"
            if metadata_path.exists():
                payload = self.store.read(metadata_path)
                payload["review"] = review_payload
                self.store.write(metadata_path, payload)
