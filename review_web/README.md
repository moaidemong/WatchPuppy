# WatchPuppy Review Web

WatchPuppy review web is the live review UI for runtime events.

## Runtime

Service:

- `watchpuppy-review-web.service`

Default bind:

- `127.0.0.1:18011`

Typical external access:

- Caddy reverse proxy on `:8088`

## Data Source

The UI syncs from:

- `/home/moai/Workspace/Codex/WatchPuppy/review_queue`

and stores reviewed rows in:

- `/home/moai/Workspace/Codex/WatchPuppy/review_web/data/review_web.sqlite3`

## Key Structure

Rows are keyed by:

- `review_key = epoch::event_id`

This allows repeated base event ids across generations without collisions.

## Current UI Responsibilities

- list runtime events
- show snapshot / clip media when present
- show classifier label and score
- update review status / label / notes
- export back into WatchPuppy manifest form

## Local Development

```bash
cd /home/moai/Workspace/Codex/WatchPuppy
/home/moai/Workspace/Codex/Runtime/Web/.venv/bin/uvicorn review_web.app.main:app --host 127.0.0.1 --port 18011
```
