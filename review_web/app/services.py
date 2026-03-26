from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from review_web.app.translations import REVIEW_LABEL_OPTIONS, REVIEW_STATUS_OPTIONS

REVIEW_EXPORT_COLUMNS = [
    "review_key",
    "event_id",
    "epoch",
    "captured_at",
    "predicted_label",
    "classifier_label",
    "classifier_score",
    "clip_path",
    "snapshot_path",
    "metadata_path",
    "review_status",
    "review_label",
    "review_notes",
]


def bootstrap_or_sync_from_watchpuppy(conn, *, watchpuppy_root: Path, current_epoch: str) -> int:
    rows = _read_review_queue_rows(watchpuppy_root / "review_queue")
    return sync_rows_into_db(conn, rows, current_epoch=current_epoch)


def sync_rows_into_db(conn, rows: list[dict[str, Any]], *, current_epoch: str) -> int:
    now = _utc_now()
    inserted = 0
    for row in rows:
        event_id = str(row.get("event_id", "")).strip()
        if not event_id:
            continue
        row_epoch = str(row.get("epoch") or current_epoch)
        review_key = f"{row_epoch}::{event_id}"
        camera_id = str(row.get("camera_id", event_id.split("-", 1)[0])).strip()
        existing = conn.execute(
            "SELECT review_status, review_label, review_notes, epoch FROM reviews WHERE review_key = ?",
            (review_key,),
        ).fetchone()
        review_status = str(row.get("review_status", "pending") or "pending")
        review_label = str(row.get("review_label", "") or "")
        review_notes = _normalize_review_notes(str(row.get("review_notes", "") or ""))
        if existing is not None:
            if existing["review_status"] != "pending" or existing["review_label"] or existing["review_notes"]:
                review_status = str(existing["review_status"])
                review_label = str(existing["review_label"])
                review_notes = _normalize_review_notes(str(existing["review_notes"]))
            conn.execute(
                """
                UPDATE reviews
                SET event_id = ?, camera_id = ?, epoch = ?, captured_at = ?, predicted_label = ?, classifier_label = ?, classifier_score = ?,
                    clip_path = ?, snapshot_path = ?, metadata_path = ?,
                    review_status = ?, review_label = ?, review_notes = ?, updated_at = ?
                WHERE review_key = ?
                """,
                (
                    event_id,
                    camera_id,
                    str(existing["epoch"] or row_epoch),
                    str(row.get("captured_at", "")),
                    str(row.get("predicted_label", "")),
                    str(row.get("classifier_label", "")),
                    _to_float(row.get("classifier_score")),
                    str(row.get("clip_path", "")),
                    str(row.get("snapshot_path", "")),
                    str(row.get("metadata_path", "")),
                    review_status,
                    review_label,
                    review_notes,
                    now,
                    review_key,
                ),
            )
            continue
        conn.execute(
            """
            INSERT INTO reviews (
                review_key, event_id, camera_id, epoch, captured_at,
                predicted_label, classifier_label, classifier_score,
                clip_path, snapshot_path, metadata_path, is_new,
                review_status, review_label, review_notes, created_at, updated_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                review_key,
                event_id,
                camera_id,
                row_epoch,
                str(row.get("captured_at", "")),
                str(row.get("predicted_label", "")),
                str(row.get("classifier_label", "")),
                _to_float(row.get("classifier_score")),
                str(row.get("clip_path", "")),
                str(row.get("snapshot_path", "")),
                str(row.get("metadata_path", "")),
                1,
                review_status,
                review_label,
                review_notes,
                now,
                now,
            ),
        )
        inserted += 1
    return inserted


def export_db_to_manifest(conn, manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        SELECT event_id, epoch, captured_at, predicted_label, classifier_label, classifier_score,
               review_key, clip_path, snapshot_path, metadata_path, review_status, review_label, review_notes
        FROM reviews
        ORDER BY captured_at DESC, event_id DESC
        """
    ).fetchall()
    with manifest_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=REVIEW_EXPORT_COLUMNS)
        writer.writeheader()
        for row in rows:
            row_dict = dict(row)
            row_dict["review_notes"] = _normalize_review_notes(str(row_dict.get("review_notes", "")))
            writer.writerow(row_dict)


def query_reviews(
    conn,
    *,
    offset: int,
    limit: int,
    camera_id: str | None,
    epoch: str | None,
    review_status: str | None,
    review_label: str | None,
    new_only: bool,
    q: str | None,
) -> tuple[int, list[dict[str, Any]]]:
    clauses: list[str] = []
    params: list[Any] = []
    if camera_id:
        clauses.append("camera_id = ?")
        params.append(camera_id)
    if epoch:
        clauses.append("epoch = ?")
        params.append(epoch)
    if review_status:
        clauses.append("review_status = ?")
        params.append(review_status)
    if review_label:
        clauses.append("review_label = ?")
        params.append(review_label)
    if new_only:
        clauses.append("is_new = 1")
    if q:
        clauses.append(
            "(event_id LIKE ? OR review_key LIKE ? OR review_notes LIKE ? OR predicted_label LIKE ? OR classifier_label LIKE ?)"
        )
        pattern = f"%{q}%"
        params.extend([pattern, pattern, pattern, pattern, pattern])
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    total = conn.execute(f"SELECT COUNT(*) FROM reviews {where_sql}", params).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT *
        FROM reviews
        {where_sql}
        ORDER BY captured_at DESC, event_id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    return total, [dict(row) for row in rows]


def list_epochs(conn) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT epoch
        FROM reviews
        WHERE epoch IS NOT NULL AND epoch <> ''
        ORDER BY epoch
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def update_review(
    conn,
    *,
    review_key: str,
    version: int,
    review_status: str,
    review_label: str,
    review_notes: str,
) -> dict[str, Any] | None:
    if review_status not in REVIEW_STATUS_OPTIONS:
        raise ValueError(f"unsupported review_status: {review_status}")
    if review_label and review_label not in REVIEW_LABEL_OPTIONS:
        raise ValueError(f"unsupported review_label: {review_label}")
    review_notes = _normalize_review_notes(review_notes)
    now = _utc_now()
    cursor = conn.execute(
        """
        UPDATE reviews
        SET review_status = ?, review_label = ?, review_notes = ?, is_new = 0, updated_at = ?, version = version + 1
        WHERE review_key = ? AND version = ?
        """,
        (review_status, review_label, review_notes, now, review_key, version),
    )
    if cursor.rowcount == 0:
        return None
    row = conn.execute("SELECT * FROM reviews WHERE review_key = ?", (review_key,)).fetchone()
    return dict(row) if row is not None else None


def media_path_for_event(conn, *, review_key: str, kind: str, watchpuppy_root: Path) -> Path | None:
    if kind not in {"clip", "snapshot"}:
        return None
    column = "clip_path" if kind == "clip" else "snapshot_path"
    row = conn.execute(f"SELECT {column} FROM reviews WHERE review_key = ?", (review_key,)).fetchone()
    if row is None or not row[column]:
        return None
    path = (watchpuppy_root / row[column]).resolve()
    try:
        path.relative_to(watchpuppy_root.resolve())
    except ValueError:
        return None
    return path if path.exists() else None


def manifest_path_from_root(watchpuppy_root: Path) -> Path:
    return watchpuppy_root / "exports" / "review_export" / "review_manifest.csv"


def _read_review_queue_rows(queue_dir: Path) -> list[dict[str, Any]]:
    if not queue_dir.exists():
        return []
    rows = []
    for path in sorted(queue_dir.glob("*.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def _normalize_review_notes(value: str | None) -> str:
    text = str(value or "")
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n")]
    return " ".join(line for line in lines if line).strip()


def _to_float(value: Any) -> float:
    if value in {None, ""}:
        return 0.0
    return float(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
