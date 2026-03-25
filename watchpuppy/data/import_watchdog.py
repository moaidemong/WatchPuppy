from __future__ import annotations

import csv
import os
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TARGET_LABEL = "failed_get_up_attempt"


@dataclass(frozen=True)
class ImportConfig:
    review_db: Path
    watchdog_root: Path
    output_root: Path
    manifest_path: Path
    epochs: tuple[str, ...]
    review_status: str = "approved"
    link_mode: str = "hardlink"
    excluded_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewRow:
    event_id: str
    epoch: str
    review_label: str
    snapshot_path: str


def fetch_review_rows(config: ImportConfig) -> list[ReviewRow]:
    conn = sqlite3.connect(config.review_db)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in config.epochs)
        query = f"""
            select event_id, epoch, review_label, snapshot_path
            from reviews
            where review_status = ?
              and epoch in ({placeholders})
            order by event_id
        """
        params: list[str] = [config.review_status, *config.epochs]
        rows = conn.execute(query, params).fetchall()
        excluded = set(config.excluded_event_ids)
        return [
            ReviewRow(
                event_id=row["event_id"],
                epoch=row["epoch"],
                review_label=row["review_label"],
                snapshot_path=row["snapshot_path"],
            )
            for row in rows
            if row["event_id"] not in excluded
        ]
    finally:
        conn.close()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def materialize_snapshot(src: Path, dst: Path, link_mode: str) -> None:
    ensure_parent(dst)
    if dst.exists() or dst.is_symlink():
        dst.unlink()

    if link_mode == "copy":
        shutil.copy2(src, dst)
        return
    if link_mode == "symlink":
        dst.symlink_to(src)
        return
    if link_mode == "hardlink":
        os.link(src, dst)
        return

    raise ValueError(f"unsupported link mode: {link_mode}")


def iter_manifest_rows(rows: Iterable[ReviewRow], config: ImportConfig) -> Iterable[dict[str, str]]:
    raw_root = config.output_root / "raw" / "watchdog_snapshots"
    for row in rows:
        src = config.watchdog_root / row.snapshot_path
        if not src.exists():
            continue

        dst = raw_root / row.epoch / f"{row.event_id}.jpg"
        materialize_snapshot(src, dst, config.link_mode)
        yield {
            "event_id": row.event_id,
            "epoch": row.epoch,
            "source_review_label": row.review_label,
            "binary_label": TARGET_LABEL if row.review_label == TARGET_LABEL else "non_target",
            "snapshot_path": str(dst.relative_to(config.output_root)),
            "source_snapshot_path": str(src),
        }


def write_manifest(rows: Iterable[dict[str, str]], manifest_path: Path) -> dict[str, int]:
    ensure_parent(manifest_path)
    fieldnames = [
        "event_id",
        "epoch",
        "source_review_label",
        "binary_label",
        "snapshot_path",
        "source_snapshot_path",
    ]
    total = 0
    positives = 0
    negatives = 0
    with manifest_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            total += 1
            if row["binary_label"] == TARGET_LABEL:
                positives += 1
            else:
                negatives += 1
    return {"total": total, "positives": positives, "negatives": negatives}


def import_watchdog_dataset(config: ImportConfig) -> dict[str, int]:
    review_rows = fetch_review_rows(config)
    manifest_rows = list(iter_manifest_rows(review_rows, config))
    stats = write_manifest(manifest_rows, config.manifest_path)
    stats["review_rows"] = len(review_rows)
    return stats
