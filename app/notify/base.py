from __future__ import annotations


class Notifier:
    def send(self, title: str, body: str) -> None:
        raise NotImplementedError
