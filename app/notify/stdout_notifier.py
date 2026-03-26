from __future__ import annotations

from app.notify.base import Notifier


class StdoutNotifier(Notifier):
    def send(self, title: str, body: str) -> None:
        print(f"[ALERT] {title}\n{body}")
