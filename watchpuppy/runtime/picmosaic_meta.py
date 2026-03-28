from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import cv2


SCHEMA_VERSION = "1.0.0"
PUBLIC_ARTIFACT_PREFIX = "/watchpuppy-artifacts"
INDEX_NAME = "picmosaic-index.json"
LEGACY_META_JSON_NAME = "picmosaic-meta.json"
LEGACY_META_JSONL_NAME = "picmosaic-meta.jsonl"


def append_picmosaic_index_online(
    *,
    artifacts_root: Path,
    metadata_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    del metadata_path

    media = payload.get("media") or {}
    watchpuppy = payload.get("watchpuppy") or {}
    cnn_prediction = watchpuppy.get("cnn_prediction") or {}

    event_dir = Path(str(media.get("event_dir", ""))).resolve()
    snapshot_path = Path(str(media.get("snapshot_path", ""))).resolve()
    shrink_path = Path(str(watchpuppy.get("shrink_path", ""))).resolve()

    if not event_dir.name.startswith("RUN"):
        return None
    if watchpuppy.get("shrink_status") != "cropped":
        return None
    if not snapshot_path.exists() or not shrink_path.exists():
        return None
    if images_are_identical(snapshot_path, shrink_path):
        return None

    remove_legacy_meta_files(artifacts_root)

    index_path = artifacts_root / INDEX_NAME
    index_payload = load_index(index_path, artifacts_root)
    items = list(index_payload.get("items", []))
    artifact_key = event_dir.name
    if any(item.get("id") == artifact_key for item in items):
        return None

    new_item = build_index_item(
        artifact_key=artifact_key,
        captured_at=normalize_captured_at(payload.get("captured_at")),
        shrink_path=shrink_path,
        artifacts_root=artifacts_root,
        cnn_prediction=cnn_prediction,
    )
    items.append(new_item)
    normalize_items_in_place(items)

    index_payload["schemaVersion"] = SCHEMA_VERSION
    index_payload["count"] = len(items)
    index_payload["sourceRoot"] = str(artifacts_root.resolve())
    index_payload["publicArtifactPrefix"] = PUBLIC_ARTIFACT_PREFIX
    index_payload["items"] = items
    write_json_atomically(index_path, index_payload)
    return new_item


def load_index(index_path: Path, artifacts_root: Path) -> dict[str, Any]:
    if index_path.exists():
        with index_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            return payload
    return {
        "schemaVersion": SCHEMA_VERSION,
        "count": 0,
        "sourceRoot": str(artifacts_root.resolve()),
        "publicArtifactPrefix": PUBLIC_ARTIFACT_PREFIX,
        "items": [],
    }


def rebuild_picmosaic_index_bulk(artifacts_root: Path) -> None:
    remove_legacy_meta_files(artifacts_root)
    index_path = artifacts_root / INDEX_NAME
    index_payload = load_index(index_path, artifacts_root)
    items = list(index_payload.get("items", []))
    normalize_items_in_place(items)
    index_payload["schemaVersion"] = SCHEMA_VERSION
    index_payload["count"] = len(items)
    index_payload["sourceRoot"] = str(artifacts_root.resolve())
    index_payload["publicArtifactPrefix"] = PUBLIC_ARTIFACT_PREFIX
    index_payload["items"] = items
    write_json_atomically(index_path, index_payload)


def append_picmosaic_record(
    *,
    artifacts_root: Path,
    metadata_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    return append_picmosaic_index_online(
        artifacts_root=artifacts_root,
        metadata_path=metadata_path,
        payload=payload,
    )


def normalize_index_file(artifacts_root: Path) -> None:
    rebuild_picmosaic_index_bulk(artifacts_root)


def build_index_item(
    *,
    artifact_key: str,
    captured_at: str,
    shrink_path: Path,
    artifacts_root: Path,
    cnn_prediction: dict[str, Any],
) -> dict[str, Any]:
    image = cv2.imread(str(shrink_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"Unable to read shrink image: {shrink_path}")
    height, width = image.shape[:2]
    colored = cnn_prediction.get("label") == "failed_get_up_attempt"
    fixed_tone = "alert" if colored else None
    public_url = to_public_artifact_url(shrink_path, artifacts_root)

    return {
        "id": artifact_key,
        "artifactKey": artifact_key,
        "sequence": 0,
        "capturedAt": captured_at,
        "width": width,
        "height": height,
        "aspectRatio": width / height if height else 0.0,
        "imagePath": str(shrink_path.resolve()),
        "thumbPath": str(shrink_path.resolve()),
        "imageUrl": public_url,
        "thumbUrl": public_url,
        "fixedTone": fixed_tone,
        "colored": colored,
    }


def normalize_items_in_place(items: list[dict[str, Any]]) -> None:
    items.sort(key=lambda item: (str(item.get("capturedAt", "")), str(item.get("id", ""))))
    for index, item in enumerate(items, start=1):
        item["sequence"] = index


def normalize_captured_at(raw: Any) -> str:
    if not raw:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    text = str(raw)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def to_public_artifact_url(path: Path, artifact_root: Path) -> str:
    relative_path = path.resolve().relative_to(artifact_root.resolve())
    return f"{PUBLIC_ARTIFACT_PREFIX}/{relative_path.as_posix()}"


def images_are_identical(original_path: Path, shrink_path: Path) -> bool:
    original = cv2.imread(str(original_path), cv2.IMREAD_UNCHANGED)
    shrink = cv2.imread(str(shrink_path), cv2.IMREAD_UNCHANGED)
    if original is None or shrink is None:
        return False
    if original.shape != shrink.shape:
        return False
    difference = cv2.absdiff(original, shrink)
    return not difference.any()


def remove_legacy_meta_files(artifacts_root: Path) -> None:
    for name in (LEGACY_META_JSON_NAME, LEGACY_META_JSONL_NAME):
        path = artifacts_root / name
        if path.exists():
            path.unlink()


def write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.chmod(tmp_path, 0o644)
    tmp_path.replace(path)
    os.chmod(path, 0o644)
