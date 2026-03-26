from __future__ import annotations

from statistics import mean
from app.core.schemas import EventFeatureVector, PoseFrame
from app.events.models import EventWindow


def _get_point(frame: PoseFrame, name: str) -> tuple[float, float, float]:
    for kp in frame.keypoints:
        if kp.name == name:
            return kp.x, kp.y, kp.confidence
    raise ValueError(f"Missing keypoint: {name}")


class FeatureExtractor:
    def extract(self, event: EventWindow, pose_frames: list[PoseFrame]) -> EventFeatureVector:
        if not pose_frames:
            raise ValueError("pose_frames must not be empty")

        shoulder_ys = [_get_point(pf, "shoulder")[1] for pf in pose_frames]
        hip_ys = [_get_point(pf, "hip")[1] for pf in pose_frames]
        confidences = [mean([kp.confidence for kp in pf.keypoints]) for pf in pose_frames]

        baseline_body_y = (shoulder_ys[0] + hip_ys[0]) / 2.0
        min_body_y = min((s + h) / 2.0 for s, h in zip(shoulder_ys, hip_ys))
        final_body_y = (shoulder_ys[-1] + hip_ys[-1]) / 2.0

        body_lift_ratio = max(0.0, baseline_body_y - min_body_y)
        achieved_progress = max(0.0, baseline_body_y - final_body_y)
        progress_ratio = achieved_progress / body_lift_ratio if body_lift_ratio > 0 else 0.0

        attempt_count = 0
        threshold = baseline_body_y - 0.04
        in_attempt = False
        for body_y in ((s + h) / 2.0 for s, h in zip(shoulder_ys, hip_ys)):
            if body_y < threshold and not in_attempt:
                attempt_count += 1
                in_attempt = True
            elif body_y >= threshold:
                in_attempt = False

        return EventFeatureVector(
            event_id=event.event_id,
            duration_s=event.duration_s,
            attempt_count=attempt_count,
            body_lift_ratio=round(body_lift_ratio, 4),
            progress_ratio=round(progress_ratio, 4),
            pose_confidence_mean=round(mean(confidences), 4),
        )
