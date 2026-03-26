from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI

app = FastAPI(title="Dog Rise Alert API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/artifacts")
def list_artifacts() -> dict[str, list[str]]:
    artifacts_dir = Path("artifacts")
    files = sorted(p.name for p in artifacts_dir.glob("*.json")) if artifacts_dir.exists() else []
    return {"artifacts": files}
