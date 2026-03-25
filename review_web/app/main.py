from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from review_web.app.db import connect, initialize_database
from review_web.app.services import (
    bootstrap_or_sync_from_watchpuppy,
    export_db_to_manifest,
    list_epochs,
    manifest_path_from_root,
    media_path_for_event,
    query_reviews,
    update_review,
)
from review_web.app.translations import REVIEW_LABEL_OPTIONS, REVIEW_STATUS_OPTIONS, TEXT_TRANSLATIONS


WATCHPUPPY_ROOT = Path(os.getenv("WATCHPUPPY_ROOT", "/home/moai/Workspace/Codex/WatchPuppy")).resolve()
DB_PATH = Path(
    os.getenv("REVIEW_WEB_DB_PATH", str(WATCHPUPPY_ROOT / "review_web" / "data" / "review_web.sqlite3"))
).resolve()
CURRENT_EPOCH = os.getenv("WATCHPUPPY_EPOCH", "RUN1").strip() or "RUN1"

initialize_database(DB_PATH)
with connect(DB_PATH) as conn:
    bootstrap_or_sync_from_watchpuppy(conn, watchpuppy_root=WATCHPUPPY_ROOT, current_epoch=CURRENT_EPOCH)

app = FastAPI(title="WatchPuppy Review Web", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(WATCHPUPPY_ROOT / "review_web" / "app" / "static")), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (WATCHPUPPY_ROOT / "review_web" / "app" / "index.html").read_text(encoding="utf-8")


@app.get("/view/clip/{event_id}", response_class=HTMLResponse)
def clip_view(event_id: str, request: Request) -> str:
    return_url = request.query_params.get("return") or "/"
    return f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Clip {event_id}</title>
    <style>
      body {{ margin: 0; font-family: "Noto Sans KR", sans-serif; background: #111827; color: #f8fafc; }}
      main {{ padding: 20px; }}
      video {{ width: 100%; max-width: 1100px; height: auto; display: block; background: #000; }}
      a {{ color: #93c5fd; }}
    </style>
  </head>
  <body>
    <main>
      <p><a href="{return_url}">리뷰 목록으로 돌아가기</a></p>
      <h1>{event_id}</h1>
      <video controls autoplay preload="metadata">
        <source src="/media/clip/{event_id}" type="video/mp4" />
      </video>
    </main>
  </body>
</html>"""


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    with connect(DB_PATH) as conn:
        epochs = list_epochs(conn)
    return {
        "current_epoch": CURRENT_EPOCH,
        "epoch_options": epochs,
        "review_status_options": REVIEW_STATUS_OPTIONS,
        "review_label_options": REVIEW_LABEL_OPTIONS,
        "translations": TEXT_TRANSLATIONS,
    }


@app.post("/api/sync")
def sync_reviews() -> dict[str, Any]:
    with connect(DB_PATH) as conn:
        inserted = bootstrap_or_sync_from_watchpuppy(conn, watchpuppy_root=WATCHPUPPY_ROOT, current_epoch=CURRENT_EPOCH)
        export_db_to_manifest(conn, manifest_path_from_root(WATCHPUPPY_ROOT))
    return {"inserted": inserted}


@app.get("/api/reviews")
def list_reviews(
    offset: int = 0,
    limit: int = 100,
    camera_id: str | None = None,
    epoch: str | None = None,
    review_status: str | None = None,
    review_label: str | None = None,
    new_only: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    new_only_flag = str(new_only or "").strip().lower() in {"1", "true", "yes", "on"}
    with connect(DB_PATH) as conn:
        total, rows = query_reviews(
            conn,
            offset=offset,
            limit=limit,
            camera_id=camera_id,
            epoch=epoch,
            review_status=review_status,
            review_label=review_label,
            new_only=new_only_flag,
            q=q,
        )
    return {"total": total, "items": rows}


@app.patch("/api/reviews/{event_id}")
def patch_review(event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    version = int(payload.get("version", 0))
    review_status = str(payload.get("review_status", "pending"))
    review_label = str(payload.get("review_label", ""))
    review_notes = str(payload.get("review_notes", ""))
    with connect(DB_PATH) as conn:
        row = update_review(
            conn,
            event_id=event_id,
            version=version,
            review_status=review_status,
            review_label=review_label,
            review_notes=review_notes,
        )
        if row is None:
            raise HTTPException(status_code=409, detail="row was updated by another user")
        export_db_to_manifest(conn, manifest_path_from_root(WATCHPUPPY_ROOT))
    return {"item": row}


@app.get("/media/{kind}/{event_id}")
def media(kind: str, event_id: str):
    with connect(DB_PATH) as conn:
        path = media_path_for_event(conn, event_id=event_id, kind=kind, watchpuppy_root=WATCHPUPPY_ROOT)
    if path is None:
        raise HTTPException(status_code=404, detail="media not found")
    media_type = "image/jpeg" if kind == "snapshot" else "video/mp4"
    return FileResponse(path, media_type=media_type)
