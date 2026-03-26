from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


FEATURE_NAMES = [
    "duration_s",
    "attempt_count",
    "body_lift_ratio",
    "progress_ratio",
    "pose_confidence_mean",
]


@dataclass(slots=True)
class Prototype:
    label: str
    center: dict[str, float]
    sample_count: int


@dataclass(slots=True)
class PrototypeModel:
    model_type: str
    feature_names: list[str]
    prototypes: list[Prototype]

    def predict(self, feature_values: dict[str, float]) -> tuple[str, float]:
        if not self.prototypes:
            raise ValueError("prototype model has no prototypes")

        distances = [
            (prototype, _euclidean_distance(prototype.center, feature_values, self.feature_names))
            for prototype in self.prototypes
        ]
        distances.sort(key=lambda item: item[1])
        best_prototype, best_distance = distances[0]
        score = 1.0 / (1.0 + best_distance)
        return best_prototype.label, round(score, 4)

    def to_dict(self) -> dict[str, object]:
        return {
            "model_type": self.model_type,
            "feature_names": self.feature_names,
            "prototypes": [asdict(prototype) for prototype in self.prototypes],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "PrototypeModel":
        return cls(
            model_type=str(payload["model_type"]),
            feature_names=[str(name) for name in payload["feature_names"]],
            prototypes=[
                Prototype(
                    label=str(item["label"]),
                    center={str(key): float(value) for key, value in dict(item["center"]).items()},
                    sample_count=int(item["sample_count"]),
                )
                for item in payload["prototypes"]
            ],
        )

    def save(self, path: str | Path) -> Path:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return file_path

    @classmethod
    def load(cls, path: str | Path) -> "PrototypeModel":
        file_path = Path(path)
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return cls.from_dict(payload)


def _euclidean_distance(
    center: dict[str, float],
    feature_values: dict[str, float],
    feature_names: list[str],
) -> float:
    total = 0.0
    for name in feature_names:
        total += (center[name] - feature_values[name]) ** 2
    return math.sqrt(total)
