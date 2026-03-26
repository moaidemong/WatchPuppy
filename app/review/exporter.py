from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import StorageSettings
from app.review.draft import build_review_draft


REVIEW_EXPORT_COLUMNS = [
    "event_id",
    "captured_at",
    "start_s",
    "end_s",
    "duration_s",
    "frame_count",
    "predicted_label",
    "classifier_label",
    "classifier_score",
    "should_alert",
    "decision_score",
    "decision_reasons",
    "clip_path",
    "snapshot_path",
    "metadata_path",
    "review_status",
    "review_label",
    "review_notes",
]


def _normalize_review_notes(value: str | None) -> str:
    text = str(value or "")
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n")]
    return " ".join(line for line in lines if line).strip()


@dataclass(slots=True)
class ReviewExportResult:
    export_dir: Path
    csv_path: Path
    jsonl_path: Path
    row_count: int


class ReviewQueueExporter:
    def __init__(self, storage: StorageSettings) -> None:
        self.storage = storage

    def export(
        self,
        export_dir: str | Path | None = None,
        *,
        auto_triage: bool = False,
    ) -> ReviewExportResult:
        target_dir = Path(export_dir) if export_dir else self.storage.exports_dir / "review_export"
        target_dir.mkdir(parents=True, exist_ok=True)

        rows = [self._build_row(path) for path in sorted(self.storage.review_queue_dir.glob("*.json"))]
        if auto_triage:
            rows = [self._apply_auto_triage(row) for row in rows]
        csv_path = target_dir / "review_manifest.csv"
        jsonl_path = target_dir / "review_manifest.jsonl"
        self._write_csv(csv_path, rows)
        self._write_jsonl(jsonl_path, rows)
        return ReviewExportResult(
            export_dir=target_dir,
            csv_path=csv_path,
            jsonl_path=jsonl_path,
            row_count=len(rows),
        )

    def _build_row(self, path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        event = payload.get("event", {})
        decision = payload.get("decision", {})
        media = payload.get("media", {})
        classifier = payload.get("classifier", {})
        return {
            "event_id": event.get("event_id"),
            "captured_at": payload.get("captured_at"),
            "start_s": event.get("start_s"),
            "end_s": event.get("end_s"),
            "duration_s": event.get("duration_s"),
            "frame_count": event.get("frame_count"),
            "predicted_label": decision.get("label"),
            "classifier_label": classifier.get("label"),
            "classifier_score": classifier.get("score"),
            "should_alert": decision.get("should_alert"),
            "decision_score": decision.get("score"),
            "decision_reasons": "|".join(decision.get("reasons", [])),
            "clip_path": media.get("clip_path"),
            "snapshot_path": media.get("snapshot_path"),
            "metadata_path": media.get("event_dir"),
            "review_status": "pending",
            "review_label": "",
            "review_notes": "",
        }

    def _apply_auto_triage(self, row: dict[str, Any]) -> dict[str, Any]:
        decision = build_review_draft(row)
        updated = row.copy()
        updated["review_status"] = decision.review_status
        updated["review_label"] = decision.review_label
        updated["review_notes"] = _normalize_review_notes(decision.review_notes)
        return updated

    def _write_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=REVIEW_EXPORT_COLUMNS)
            writer.writeheader()
            writer.writerows(
                {
                    **row,
                    "review_notes": _normalize_review_notes(row.get("review_notes", "")),
                }
                for row in rows
            )

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as file_obj:
            for row in rows:
                file_obj.write(json.dumps(row, ensure_ascii=False) + "\n")
