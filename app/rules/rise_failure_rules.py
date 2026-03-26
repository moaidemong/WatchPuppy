from __future__ import annotations

from dataclasses import dataclass
from app.core.schemas import EventFeatureVector


@dataclass(slots=True)
class RuleDecision:
    should_alert: bool
    should_review: bool
    label: str
    reasons: list[str]
    score: float


@dataclass(slots=True)
class RiseFailureRuleConfig:
    failed_attempt_min_attempts: int
    failed_attempt_min_duration_seconds: float
    min_body_lift_ratio: float
    max_progress_ratio: float


class RiseFailureRuleEngine:
    def __init__(self, config: RiseFailureRuleConfig) -> None:
        self.config = config

    def evaluate(self, features: EventFeatureVector) -> RuleDecision:
        reasons: list[str] = []
        score = 0.0

        if features.attempt_count >= self.config.failed_attempt_min_attempts:
            reasons.append("multiple rise attempts detected")
            score += 0.35
        if features.duration_s >= self.config.failed_attempt_min_duration_seconds:
            reasons.append("long-duration struggle")
            score += 0.25
        if features.body_lift_ratio >= self.config.min_body_lift_ratio:
            reasons.append("body lift effort observed")
            score += 0.20
        if features.progress_ratio <= self.config.max_progress_ratio:
            reasons.append("insufficient progress to standing")
            score += 0.20

        should_alert = len(reasons) == 4
        should_review = len(reasons) >= 2
        label = "failed_get_up_attempt" if should_alert else "no_alert"
        return RuleDecision(
            should_alert=should_alert,
            should_review=should_review,
            label=label,
            reasons=reasons,
            score=round(score, 3),
        )
