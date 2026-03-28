#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-prefix",
        default="RUN1__",
        help="Only evaluate artifact directories whose names start with this prefix.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where summary.json, all_predictions.csv, and label_changes.csv are written.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Decision threshold for failed_get_up_attempt.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo))

    import torch
    from PIL import Image
    from watchpuppy.models import build_model
    from watchpuppy.training import create_image_transform

    artifacts_dir = repo / "artifacts"
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = (
        repo
        / "data"
        / "interim"
        / "models"
        / "final_shrink_mobilenet5"
        / "failed_get_up_mobilenet_v3_small.pt"
    )
    model = build_model("mobilenet_v3_small", num_classes=2)
    state = torch.load(model_path, map_location="cpu")
    model.load_state_dict(state)
    model.to("cpu")
    model.eval()
    transform = create_image_transform(96, train=False)

    summary = {
        "scope_prefix": args.artifact_prefix,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "model_path": str(model_path),
        "threshold": args.threshold,
        "artifact_dirs_seen": 0,
        "artifacts_evaluated": 0,
        "missing_shrink": 0,
        "missing_metadata": 0,
        "old_positive_new_negative": 0,
        "old_negative_new_positive": 0,
        "both_positive": 0,
        "both_negative": 0,
        "old_positive_total": 0,
        "new_positive_total": 0,
    }
    all_rows: list[dict[str, object]] = []
    change_rows: list[dict[str, object]] = []

    artifact_dirs = sorted(
        p for p in artifacts_dir.iterdir() if p.is_dir() and p.name.startswith(args.artifact_prefix)
    )
    for artifact_dir in artifact_dirs:
        summary["artifact_dirs_seen"] += 1
        shrink = artifact_dir / "snapshot_shrink.jpg"
        metadata_path = artifact_dir / "metadata.json"
        if not shrink.exists():
            summary["missing_shrink"] += 1
            continue
        if not metadata_path.exists():
            summary["missing_metadata"] += 1
            continue
        try:
            metadata = json.loads(metadata_path.read_text())
        except Exception:
            summary["missing_metadata"] += 1
            continue

        old_pred = (((metadata.get("watchpuppy") or {}).get("cnn_prediction")) or {})
        old_label = old_pred.get("label")
        old_score = old_pred.get("score")
        image = Image.open(shrink).convert("RGB")
        tensor = transform(image).unsqueeze(0)
        with torch.no_grad():
            new_score = float(torch.softmax(model(tensor), dim=1)[0, 1].item())
        new_label = "failed_get_up_attempt" if new_score >= args.threshold else "non_target"
        summary["artifacts_evaluated"] += 1

        old_pos = old_label == "failed_get_up_attempt"
        new_pos = new_label == "failed_get_up_attempt"
        if old_pos:
            summary["old_positive_total"] += 1
        if new_pos:
            summary["new_positive_total"] += 1
        if old_pos and new_pos:
            summary["both_positive"] += 1
        elif (not old_pos) and (not new_pos):
            summary["both_negative"] += 1
        elif old_pos and (not new_pos):
            summary["old_positive_new_negative"] += 1
        elif (not old_pos) and new_pos:
            summary["old_negative_new_positive"] += 1

        parts = artifact_dir.name.split("__", 2)
        event_id = parts[1] if len(parts) > 1 else artifact_dir.name
        row = {
            "artifact_key": artifact_dir.name,
            "event_id": event_id,
            "shrink_path": str(shrink),
            "old_label": old_label,
            "old_score": old_score,
            "new_label": new_label,
            "new_score": new_score,
            "changed": old_label != new_label,
        }
        all_rows.append(row)
        if row["changed"]:
            change_rows.append(row)

    summary["changed_total"] = len(change_rows)

    fields = [
        "artifact_key",
        "event_id",
        "shrink_path",
        "old_label",
        "old_score",
        "new_label",
        "new_score",
        "changed",
    ]
    with (output_dir / "all_predictions.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)
    with (output_dir / "label_changes.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(change_rows)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
