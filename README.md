# WatchPuppy

WatchPuppy is a low-power edge AI pipeline for a single operational question:

- `failed_get_up_attempt`
- or `non_target`

The current runtime is live and built around:

- TAPO ONVIF `pet` events only
- Hailo/YOLO front-stage shrink generation
- `mobilenet_v3_small` snapshot classifier
- Telegram alerting
- review web
- PicMosaic upstream index generation

## Current Runtime Flow

```text
TAPO ONVIF pet event
  -> WatchPuppy collector
  -> WatchDog-derived snapshot capture (internalized app/)
  -> YOLO/Hailo dog-only shrink
  -> context/detection filtering
  -> always-on CNN inference server
  -> metadata + review_queue + optional Telegram
  -> PicMosaic index append
```

## Current Operational Rules

- trigger source: `pet` only
- general `motion`: ignored
- only YOLO `dog` detections may proceed to CNN
- `person` / `cat` context may block downstream classification
- clip capture is disabled
- runtime is effectively snapshot-only

## Runtime Services

- `watchpuppy-review-web.service`
- `watchpuppy-cnn-inference.service`
- `watchpuppy-onvif-gated@a.service`
- `watchpuppy-onvif-gated@b.service`
- `watchpuppy-onvif-gated@c.service`

## Shared Runtime Environments

- Hailo runtime:
  - `/home/moai/Workspace/Codex/Runtime/Hailo/.venv`
- PyTorch runtime:
  - `/home/moai/Workspace/Codex/Runtime/PyTorch/.venv`
- Web runtime:
  - `/home/moai/Workspace/Codex/Runtime/Web/.venv`

## Main Paths

- artifacts:
  - `/home/moai/Workspace/Codex/WatchPuppy/artifacts`
- review queue:
  - `/home/moai/Workspace/Codex/WatchPuppy/review_queue`
- logs:
  - `/home/moai/Workspace/Codex/WatchPuppy/logs`
- runtime config:
  - `/home/moai/Workspace/Codex/WatchPuppy/configs/watchpuppy.tapo.yaml`
- service env:
  - `/home/moai/Workspace/Codex/WatchPuppy/configs/watchpuppy.env`

## Model

Current production checkpoint:

- [failed_get_up_mobilenet_v3_small.pt](/home/moai/Workspace/Codex/WatchPuppy/data/interim/models/final_shrink_mobilenet5/failed_get_up_mobilenet_v3_small.pt)

Current serving shape:

- input: `snapshot_shrink.jpg`
- image size: `96 x 96`
- backbone: `mobilenet_v3_small`
- threshold: `0.8`

## Training Data

Initial training truth came from reviewed WatchDog data:

- source review DB:
  - `/home/moai/Workspace/Codex/WatchDog/review_web/data/review_web.sqlite3`
- included epochs:
  - `Gen1` through `Gen5`
- included review status:
  - `approved`
- positive class:
  - `failed_get_up_attempt`
- negative class:
  - every other approved label

## Important Scripts

- import WatchDog dataset:
  - `python scripts/import_watchdog_dataset.py`
- create splits:
  - `python scripts/create_dataset_splits.py`
- train CNN:
  - `python scripts/train_cnn.py`
- rebuild PicMosaic index in bulk:
  - `python scripts/rebuild_picmosaic_index.py`
- inspect Telegram updates:
  - `./scripts/get_telegram_updates.py`
- send Telegram image test:
  - `./scripts/send_telegram_test_alert.py`

## PicMosaic Upstream

WatchPuppy now maintains only:

- `/home/moai/Workspace/Codex/WatchPuppy/artifacts/picmosaic-index.json`

Rules:

- `RUN*__...` artifacts only
- `shrink_status == "cropped"` only
- exclude events where `snapshot.jpg` and `snapshot_shrink.jpg` are identical
- file order is `old first, latest last`
- PicMosaic reverses in memory for UI display

Bulk rebuild and online append are intentionally separated:

- online:
  - `append_picmosaic_index_online(...)`
- bulk:
  - `rebuild_picmosaic_index_bulk(...)`

## Logging

Structured daily logs:

- `backbone-YYYYMMDD.log`
- `front_yolo_process-YYYYMMDD.log`
- `backend_cnn_process-YYYYMMDD.log`

Camera raw stderr logs:

- `hef_camera_a-YYYYMMDD.log`
- `hef_camera_b-YYYYMMDD.log`
- `hef_camera_c-YYYYMMDD.log`

All structured logs include:

- datetime
- `trx:<transaction-id>`
- `prod|debug` mode support

## Review Web

The review UI stores records by:

- `review_key = epoch::event_id`

This allows the same base `event_id` to coexist across generations.
