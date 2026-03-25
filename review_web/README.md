# WatchDog Review Web

SQLite-backed review UI for family-assisted label correction.

Run locally:

```bash
cd /home/moai/Workspace/Codex/WatchDog
source .venv/bin/activate
uvicorn review_web.app.main:app --host 127.0.0.1 --port 8010
uvicorn review_web.app.main:app --host 127.0.0.1 --port 18010
```
