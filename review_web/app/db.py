from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    review_key TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    epoch TEXT NOT NULL DEFAULT '',
    captured_at TEXT,
    predicted_label TEXT NOT NULL DEFAULT '',
    classifier_label TEXT NOT NULL DEFAULT '',
    classifier_score REAL NOT NULL DEFAULT 0,
    clip_path TEXT NOT NULL DEFAULT '',
    snapshot_path TEXT NOT NULL DEFAULT '',
    metadata_path TEXT NOT NULL DEFAULT '',
    is_new INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'pending',
    review_label TEXT NOT NULL DEFAULT '',
    review_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_reviews_event_id ON reviews(event_id);
CREATE INDEX IF NOT EXISTS idx_reviews_camera_id ON reviews(camera_id);
CREATE INDEX IF NOT EXISTS idx_reviews_epoch ON reviews(epoch);
CREATE INDEX IF NOT EXISTS idx_reviews_review_status ON reviews(review_status);
CREATE INDEX IF NOT EXISTS idx_reviews_review_label ON reviews(review_label);
CREATE INDEX IF NOT EXISTS idx_reviews_is_new ON reviews(is_new);
"""


def initialize_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        _migrate_reviews_table(conn)
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def connect(db_path: Path):
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    try:
        yield conn
    finally:
        conn.close()


def _migrate_reviews_table(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='reviews'"
    ).fetchone()
    if table_exists is None:
        return
    columns = [row[1] for row in conn.execute("PRAGMA table_info(reviews)").fetchall()]
    if "review_key" in columns:
        return

    conn.execute("ALTER TABLE reviews RENAME TO reviews_old")
    conn.executescript(SCHEMA)
    conn.execute(
        """
        INSERT INTO reviews (
            review_key, event_id, camera_id, epoch, captured_at,
            predicted_label, classifier_label, classifier_score,
            clip_path, snapshot_path, metadata_path, is_new,
            review_status, review_label, review_notes, created_at, updated_at, version
        )
        SELECT
            CASE
                WHEN COALESCE(epoch, '') = '' THEN '::' || event_id
                ELSE epoch || '::' || event_id
            END AS review_key,
            event_id, camera_id, epoch, captured_at,
            predicted_label, classifier_label, classifier_score,
            clip_path, snapshot_path, metadata_path, is_new,
            review_status, review_label, review_notes, created_at, updated_at, version
        FROM reviews_old
        """
    )
    conn.execute("DROP TABLE reviews_old")
