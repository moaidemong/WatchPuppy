# Data Import

WatchPuppy starts from reviewed WatchDog artifacts.

Current source of truth:

- review DB:
  - `/home/moai/Workspace/Codex/WatchDog/review_web/data/review_web.sqlite3`
- epochs:
  - `Gen1` through `Gen5`
- review status:
  - `approved`

Binary target mapping:

- `failed_get_up_attempt` -> positive
- all other approved review labels -> `non_target`

The import script creates:

- local image assets under `data/raw/watchdog_snapshots/`
- a binary CSV manifest under `data/processed/`

Default command:

```bash
python scripts/import_watchdog_dataset.py
```
