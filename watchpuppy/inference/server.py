from __future__ import annotations

import json
import logging
from pathlib import Path
import threading
from typing import Any


logger = logging.getLogger("watchpuppy.backend_cnn_process")


class LoadedSnapshotModel:
    def __init__(
        self,
        *,
        model_name: str,
        model_path: Path,
        image_size: int,
        device: str = "cpu",
    ) -> None:
        import torch
        from watchpuppy.models import build_model

        self._torch = torch
        self.device = device
        self.model_name = model_name
        self.model_path = Path(model_path)
        self.image_size = int(image_size)
        self.model = build_model(model_name, num_classes=2)
        state = torch.load(self.model_path, map_location=device)
        self.model.load_state_dict(state)
        self.model.to(device)
        self.model.eval()
        self._transform = None
        self._lock = threading.Lock()

    def predict(self, *, image_path: Path, threshold: float) -> dict[str, Any]:
        from PIL import Image
        from watchpuppy.training import create_image_transform

        if self._transform is None:
            self._transform = create_image_transform(self.image_size, train=False)

        image_path = Path(image_path)
        image = Image.open(image_path).convert("RGB")
        tensor = self._transform(image).unsqueeze(0).to(self.device)

        with self._lock:
            with self._torch.no_grad():
                score = float(self._torch.softmax(self.model(tensor), dim=1)[0, 1].item())

        label = "failed_get_up_attempt" if score >= threshold else "non_target"
        prediction = {"label": label, "score": score, "threshold": float(threshold)}
        logger.info(
            json.dumps(
                {
                    "phase": "serve_prediction",
                    "image_path": str(image_path),
                    "prediction": prediction,
                },
                ensure_ascii=False,
            )
        )
        return prediction
