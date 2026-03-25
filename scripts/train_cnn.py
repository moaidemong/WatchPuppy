#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a snapshot CNN binary classifier for failed_get_up_attempt."
    )
    parser.add_argument(
        "--train-manifest",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/splits/train.csv",
    )
    parser.add_argument(
        "--val-manifest",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/splits/val.csv",
    )
    parser.add_argument(
        "--test-manifest",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/processed/splits/test.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="/home/moai/Workspace/Codex/WatchPuppy/data/interim/models",
    )
    parser.add_argument("--model-name", default="simple_cnn")
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--device", default="cpu")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        import torch
        from torch.utils.data import DataLoader
    except ModuleNotFoundError as exc:
        print(
            "PyTorch is not installed in this environment. Install project dependencies first.",
            file=sys.stderr,
        )
        print(f"missing module: {exc.name}", file=sys.stderr)
        return 1

    from watchpuppy.models import build_model
    from watchpuppy.training import TorchSnapshotDataset, create_image_transform, evaluate_epoch, fit

    train_dataset = TorchSnapshotDataset(
        manifest_path=Path(args.train_manifest),
        transform=create_image_transform(args.image_size, train=True),
    )
    val_dataset = TorchSnapshotDataset(
        manifest_path=Path(args.val_manifest),
        transform=create_image_transform(args.image_size, train=False),
    )
    test_dataset = TorchSnapshotDataset(
        manifest_path=Path(args.test_manifest),
        transform=create_image_transform(args.image_size, train=False),
    )

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)

    model = build_model(model_name=args.model_name, num_classes=2)
    history = fit(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=args.device,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
    )
    test_metrics = evaluate_epoch(model, test_loader, device=args.device)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "failed_get_up_simple_cnn.pt"
    metrics_path = output_dir / "failed_get_up_simple_cnn.metrics.json"
    torch.save(model.state_dict(), model_path)
    metrics_path.write_text(
        json.dumps(
            {
                "model_name": args.model_name,
                "image_size": args.image_size,
                "batch_size": args.batch_size,
                "epochs": args.epochs,
                "learning_rate": args.learning_rate,
                "device": args.device,
                "history": history,
                "test_metrics": test_metrics,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "model_path": str(model_path),
                "metrics_path": str(metrics_path),
                "test_metrics": test_metrics,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
