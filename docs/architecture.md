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

Separate optional viewing path:

```text
TAPO RTSP
  -> ffmpeg relay
  -> per-camera HTTP MPEG-TS endpoint
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
- RTSP persistent connection enabled for the OpenCV ingest backend
- on trigger, WatchPuppy reuses the live RTSP session and grabs a fresh frame instead of reconnecting

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

### 6. Telegram Alerting

Role:

- notify operators when runtime predicts `failed_get_up_attempt`

Current mode:

- async queueing from the main pipeline
- recipient sends in parallel
- default delivery is text-only
- photo delivery is optional through env

### 7. Stream Relay Layer

Role:

- provide lightweight operator viewing endpoints
- keep viewing separated from the detection runtime

Current implementation:

- systemd units:
  - `watchpuppy-stream@a.service`
  - `watchpuppy-stream@b.service`
  - `watchpuppy-stream@c.service`
- port mapping:
  - `a -> 10111`
  - `b -> 10112`
  - `c -> 10113`
- transport:
  - RTSP input
  - `ffmpeg` relay
  - HTTP MPEG-TS output at `/stream.ts`

This replaced the earlier OpenCV decode/re-encode MJPEG server.

### 8. PicMosaic Upstream

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
- Telegram no longer blocks the main detection path
- default Telegram delivery is text-only
- structured logging and camera stderr logging are intentionally separated
- stream relay is intentionally separate from ONVIF/CNN services
