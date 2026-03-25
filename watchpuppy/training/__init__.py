"""Training entry points for WatchPuppy."""
from watchpuppy.training.data import TorchSnapshotDataset, create_image_transform
from watchpuppy.training.engine import evaluate_epoch, fit

__all__ = [
    "TorchSnapshotDataset",
    "create_image_transform",
    "evaluate_epoch",
    "fit",
]
