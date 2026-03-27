# Architecture

## Runtime Summary

WatchPuppy is no longer just an offline training sandbox.
It currently operates as a live edge pipeline.

```text
ONVIF pet trigger
  -> capture snapshot
  -> YOLO/Hailo shrink
  -> dog-only gate
  -> always-on CNN inference
  -> metadata/review_queue/logging
  -> Telegram alert
  -> PicMosaic index append
```

## Main Components

### 1. Collector Runtime

Entry:

- [run_onvif_watchpuppy_pipeline.py](/home/moai/Workspace/Codex/WatchPuppy/scripts/run_onvif_watchpuppy_pipeline.py)

Role:

- subscribe to TAPO ONVIF pullpoint
- accept `pet` triggers only
- apply cooldown
- invoke snapshot capture and downstream processing

### 2. Capture Layer

Current implementation still uses the internalized WatchDog `app/` tree.

Role:

- acquire the event snapshot
- persist `metadata.json`
- create per-event artifact directory

Current mode:

- clip disabled
- snapshot-oriented upstream

### 3. Front YOLO Stage

Key module:

- [yolo_shrink.py](/home/moai/Workspace/Codex/WatchPuppy/watchpuppy/upstream/yolo_shrink.py)

Role:

- run Hailo/YOLO on `snapshot.jpg`
- crop a `snapshot_shrink.jpg`
- reject non-`dog` detections before CNN
- preserve context labels for logging/metadata

### 4. CNN Stage

Serving mode:

- always-on inference server

Key modules:

- [run_cnn_inference_server.py](/home/moai/Workspace/Codex/WatchPuppy/scripts/run_cnn_inference_server.py)
- [server.py](/home/moai/Workspace/Codex/WatchPuppy/watchpuppy/inference/server.py)
- [pipeline.py](/home/moai/Workspace/Codex/WatchPuppy/watchpuppy/runtime/pipeline.py)

Role:

- consume `snapshot_shrink.jpg`
- return `failed_get_up_attempt` vs `non_target`
- avoid per-event model reload

### 5. Review Layer

Role:

- show runtime events
- allow human review/correction
- preserve generation-separated keys

Current key:

- `review_key = epoch::event_id`

### 6. PicMosaic Upstream

Role:

- maintain final upstream service file:
  - `/home/moai/Workspace/Codex/WatchPuppy/artifacts/picmosaic-index.json`

Rules:

- include only `RUN*__...`
- include only true cropped shrink images
- exclude identical original/shrink pairs
- keep file order:
  - `old first`
  - `latest last`

## Bulk vs Online Separation

This is explicitly split now.

### Online

- append one event into `picmosaic-index.json`
- used by live pipeline only
- function:
  - `append_picmosaic_index_online(...)`

### Bulk

- normalize/rebuild index intentionally as a separate operation
- used only for one-shot maintenance or backfill
- function:
  - `rebuild_picmosaic_index_bulk(...)`
- script:
  - [rebuild_picmosaic_index.py](/home/moai/Workspace/Codex/WatchPuppy/scripts/rebuild_picmosaic_index.py)

## Shared Runtime Environments

### Hailo Runtime

- ONVIF
- OpenCV
- Hailo detector execution

Path:

- `/home/moai/Workspace/Codex/Runtime/Hailo/.venv`

### PyTorch Runtime

- torch
- torchvision
- CNN inference/training

Path:

- `/home/moai/Workspace/Codex/Runtime/PyTorch/.venv`

### Web Runtime

- FastAPI
- Uvicorn

Path:

- `/home/moai/Workspace/Codex/Runtime/Web/.venv`

## Operational Notes

- current trigger source is `pet` only
- general motion is disabled
- detector context may still block downstream decisions
- Telegram alerting is optional and env-driven
- structured logging and camera stderr logging are intentionally separated
