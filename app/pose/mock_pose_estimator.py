from __future__ import annotations

from app.core.schemas import Keypoint, PoseFrame
from app.events.models import EventWindow
from app.pose.base import PoseEstimator


class MockPoseEstimator(PoseEstimator):
    """Generates a deterministic failed-rise-like sequence."""

    def estimate(self, event: EventWindow) -> list[PoseFrame]:
        results: list[PoseFrame] = []
        total = len(event.frames)
        for i, frame in enumerate(event.frames):
            phase = i / max(1, total - 1)
            # body lift oscillates but ends with low progress
            shoulder_y = 0.70 - (0.12 if i % 4 in (1, 2) else 0.02)
            hip_y = 0.78 - (0.06 if i % 4 in (1, 2) else 0.01)
            nose_y = 0.55 - (0.10 if i % 4 in (1, 2) else 0.03)
            if phase > 0.8:
                shoulder_y = 0.68
                hip_y = 0.76
                nose_y = 0.53
            results.append(
                PoseFrame(
                    timestamp_s=frame.timestamp_s,
                    keypoints=[
                        Keypoint(name="nose", x=0.42, y=nose_y, confidence=0.94),
                        Keypoint(name="shoulder", x=0.45, y=shoulder_y, confidence=0.93),
                        Keypoint(name="hip", x=0.55, y=hip_y, confidence=0.92),
                    ],
                )
            )
        return results
