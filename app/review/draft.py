from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ReviewDraftDecision:
    review_status: str
    review_label: str
    review_notes: str


def build_review_draft(row: dict[str, Any]) -> ReviewDraftDecision:
    predicted_label = str(row.get("predicted_label", "") or "")
    should_alert = _to_bool(row.get("should_alert"))
    decision_score = _to_float(row.get("decision_score"))
    duration_s = _to_float(row.get("duration_s"))
    reasons = _parse_reasons(row.get("decision_reasons"))

    if (
        predicted_label == "failed_get_up_attempt"
        and should_alert
        and decision_score >= 1.0
        and duration_s >= 10.0
    ):
        return ReviewDraftDecision(
            review_status="approved",
            review_label="failed_get_up_attempt",
            review_notes="auto-triage: high-confidence long-duration rise-failure candidate",
        )

    if predicted_label == "no_alert" and not reasons and duration_s <= 1.5:
        return ReviewDraftDecision(
            review_status="approved",
            review_label="normal_rest",
            review_notes="auto-triage: short calm non-alert event",
        )

    if (
        predicted_label == "no_alert"
        and reasons == {"body lift effort observed", "insufficient progress to standing"}
        and duration_s < 5.0
    ):
        return ReviewDraftDecision(
            review_status="pending",
            review_label="restless_while_lying",
            review_notes="auto-draft: low-severity body movement while lying; verify from clip",
        )

    if predicted_label == "no_alert" and "multiple rise attempts detected" in reasons and duration_s >= 5.0:
        return ReviewDraftDecision(
            review_status="pending",
            review_label="unclear",
            review_notes="auto-draft: repeated effort without alert threshold; review carefully",
        )

    return ReviewDraftDecision(
        review_status="pending",
        review_label="unclear",
        review_notes="auto-draft: needs human review",
    )


def _parse_reasons(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {item for item in value.split("|") if item}
    return {str(item) for item in value if str(item)}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


def _to_float(value: Any) -> float:
    if value in {None, ""}:
        return 0.0
    return float(value)
