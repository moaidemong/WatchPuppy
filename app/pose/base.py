from __future__ import annotations

from app.core.schemas import PoseFrame
from app.events.models import EventWindow


class PoseEstimator:
    def estimate(self, event: EventWindow) -> list[PoseFrame]:
        raise NotImplementedError
