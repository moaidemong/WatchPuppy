from __future__ import annotations

from pathlib import Path

from app.classifier.model import PrototypeModel
from app.core.schemas import EventFeatureVector


def infer_label(
    features: EventFeatureVector,
    model_path: str | Path | None = None,
) -> tuple[str, float]:
    if model_path is not None and Path(model_path).exists():
        model = PrototypeModel.load(model_path)
        return model.predict(features.to_dict())

    if features.attempt_count >= 2 and features.progress_ratio < 0.5:
        return "failed_get_up_attempt", 0.65
    return "no_alert", 0.35
