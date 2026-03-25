# WatchPuppy

WatchPuppy is a fresh follow-up project to WatchDog.

The current goal is intentionally narrow:

- input: `snapshot.jpg`
- upstream gate: YOLO dog detection only
- discard frames with other objects such as person/cat
- downstream model: CNN image classifier
- target label: `failed_get_up_attempt`
- training truth: reviewed labels from WatchDog `Gen1` through `Gen5`

## Scope

This project is not trying to solve broad pet behavior recognition.
It focuses on a single binary question:

- `failed_get_up_attempt`
- `non_target`

## Planned Structure

```text
WatchPuppy/
  data/
    raw/
    interim/
    processed/
  docs/
  scripts/
  watchpuppy/
    data/
    models/
    training/
    inference/
```

## Initial Plan

1. Export reviewed WatchDog snapshots and labels from `Gen1` to `Gen5`
2. Build a clean binary dataset:
   - positive: `failed_get_up_attempt`
   - negative: everything else
3. Train a small pretrained CNN on snapshots
4. Evaluate on held-out samples before any runtime integration

## Current Dataset Import Contract

- source review DB:
  - `/home/moai/Workspace/Codex/WatchDog/review_web/data/review_web.sqlite3`
- source artifacts root:
  - `/home/moai/Workspace/Codex/WatchDog`
- included epochs:
  - `Gen1`, `Gen2`, `Gen3`, `Gen4`, `Gen5`
- included review status:
  - `approved`
- binary target:
  - positive: `failed_get_up_attempt`
  - negative: every other approved review label

## Local Import

Create a local binary snapshot dataset with:

```bash
python scripts/import_watchdog_dataset.py
```

By default this will:

- read reviewed labels from WatchDog
- import `snapshot.jpg` into `data/raw/watchdog_snapshots/`
- create hard links when possible
- write a binary manifest to:
  - `data/processed/gen1_gen5_failed_get_up_binary.csv`
