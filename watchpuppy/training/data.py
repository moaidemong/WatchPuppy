from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from watchpuppy.datasets.binary import (
    BinarySnapshotDatasetEntry,
    load_binary_snapshot_entries_from_manifest,
)


def create_image_transform(image_size: int = 224, train: bool = False):
    from torchvision import transforms

    if train:
        return transforms.Compose(
            [
                transforms.Resize((image_size, image_size)),
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.ColorJitter(brightness=0.15, contrast=0.15),
                transforms.ToTensor(),
            ]
        )

    return transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
        ]
    )


class TorchSnapshotDataset:
    def __init__(
        self,
        manifest_path: Path,
        transform=None,
    ) -> None:
        self.entries = load_binary_snapshot_entries_from_manifest(manifest_path)
        self.transform = transform

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int):
        from PIL import Image

        entry = self.entries[index]
        image = Image.open(entry.image_path).convert("RGB")
        if self.transform is not None:
            image = self.transform(image)
        return image, entry.label, entry.event_id

    def class_counts(self) -> dict[int, int]:
        counts = {0: 0, 1: 0}
        for entry in self.entries:
            counts[entry.label] = counts.get(entry.label, 0) + 1
        return counts


def compute_balanced_class_weights(dataset: TorchSnapshotDataset) -> tuple[float, float]:
    counts = dataset.class_counts()
    total = counts[0] + counts[1]
    if total == 0:
        raise ValueError("dataset is empty")
    weight_0 = total / (2 * max(counts[0], 1))
    weight_1 = total / (2 * max(counts[1], 1))
    return float(weight_0), float(weight_1)


@dataclass(frozen=True)
class SplitPaths:
    train: Path
    val: Path
    test: Path
