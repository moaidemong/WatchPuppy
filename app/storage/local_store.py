from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonFileStore:
    def write(self, path: str | Path, payload: dict[str, Any]) -> None:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def read(self, path: str | Path) -> dict[str, Any]:
        file_path = Path(path)
        return json.loads(file_path.read_text(encoding="utf-8"))
