from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import MotionGateSettings
from app.ingest.frame_source import Frame


@dataclass(slots=True)
class MotionGateDecision:
    should_process: bool
    changed_ratio: float


class MotionGate:
    """Simple ROI-based frame differencing gate for edge deployments."""

    def __init__(self, settings: MotionGateSettings) -> None:
        self.settings = settings
        self._previous_gray = None

    def evaluate(self, frame: Frame) -> MotionGateDecision:
        if not self.settings.enabled:
            return MotionGateDecision(should_process=True, changed_ratio=1.0)

        image = frame.payload
        if image is None or not hasattr(image, "shape"):
            return MotionGateDecision(should_process=True, changed_ratio=1.0)

        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - runtime dependent
            raise RuntimeError("OpenCV is required for motion gate evaluation.") from exc

        cropped = self._crop_roi(image)
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

        if self._previous_gray is None:
            self._previous_gray = gray
            return MotionGateDecision(should_process=True, changed_ratio=1.0)

        diff = cv2.absdiff(self._previous_gray, gray)
        _, mask = cv2.threshold(diff, self.settings.pixel_diff_threshold, 255, cv2.THRESH_BINARY)
        changed_ratio = float(mask.mean() / 255.0)
        self._previous_gray = gray
        return MotionGateDecision(
            should_process=changed_ratio >= self.settings.min_changed_ratio,
            changed_ratio=round(changed_ratio, 6),
        )

    def _crop_roi(self, image: Any) -> Any:
        roi = self.settings.roi
        if roi is None:
            return image

        height, width = image.shape[:2]
        x1 = max(0, min(width, int(roi[0] * width)))
        y1 = max(0, min(height, int(roi[1] * height)))
        x2 = max(x1 + 1, min(width, int(roi[2] * width)))
        y2 = max(y1 + 1, min(height, int(roi[3] * height)))
        return image[y1:y2, x1:x2]
