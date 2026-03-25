from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SnapshotPrediction:
    label: str
    score: float
    threshold: float


def predict_snapshot(
    *,
    model_name: str,
    model_path: Path,
    image_path: Path,
    image_size: int,
    threshold: float,
    device: str = "cpu",
) -> SnapshotPrediction:
    import torch
    from PIL import Image

    from watchpuppy.models import build_model
    from watchpuppy.training import create_image_transform

    model = build_model(model_name, num_classes=2)
    state = torch.load(model_path, map_location=device)
    model.load_state_dict(state)
    model.to(device)
    model.eval()

    image = Image.open(image_path).convert("RGB")
    tensor = create_image_transform(image_size, train=False)(image).unsqueeze(0).to(device)

    with torch.no_grad():
        score = float(torch.softmax(model(tensor), dim=1)[0, 1].item())
    label = "failed_get_up_attempt" if score >= threshold else "non_target"
    return SnapshotPrediction(label=label, score=score, threshold=threshold)
