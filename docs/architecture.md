# Architecture

WatchPuppy is intentionally split around an input connector boundary.

## Goal

- current model input: `snapshot.jpg`
- current target: `failed_get_up_attempt`
- current truth source: reviewed WatchDog `Gen1` to `Gen5`

## Layers

### 1. Upstream

Produces `SnapshotRecord` items.

Current:

- WatchDog reviewed snapshot manifest

Future:

- TAPO pull + YOLO dog-only event connector

### 2. Dataset

Turns upstream records into train/eval-ready entries.

Current:

- binary dataset:
  - positive: `failed_get_up_attempt`
  - negative: `non_target`
- stratified split manifests:
  - `train.csv`
  - `val.csv`
  - `test.csv`

### 3. Model

CNN image classifier on dog snapshots.

### 4. Runtime

Later runtime integration should depend on the same `SnapshotRecord`
shape so that TAPO online input and WatchDog offline snapshots can share
the downstream code path.
