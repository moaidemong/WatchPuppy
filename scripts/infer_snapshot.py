#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from watchpuppy.inference.cnn_infer import predict_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run WatchPuppy CNN inference on a single snapshot.")
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--image-path", required=True)
    parser.add_argument("--image-size", type=int, required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--device", default="cpu")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    prediction = predict_snapshot(
        model_name=args.model_name,
        model_path=Path(args.model_path),
        image_path=Path(args.image_path),
        image_size=args.image_size,
        threshold=args.threshold,
        device=args.device,
    )
    print(json.dumps({"label": prediction.label, "score": prediction.score, "threshold": prediction.threshold}))


if __name__ == "__main__":
    main()
