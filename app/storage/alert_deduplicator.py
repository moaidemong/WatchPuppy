from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(slots=True)
class AlertDeduplicator:
    cooldown_seconds: float
    _last_sent_at: Dict[str, float] = field(default_factory=dict)

    def should_send(self, alert_key: str, now_s: float) -> bool:
        previous = self._last_sent_at.get(alert_key)
        if previous is None or (now_s - previous) >= self.cooldown_seconds:
            self._last_sent_at[alert_key] = now_s
            return True
        return False
