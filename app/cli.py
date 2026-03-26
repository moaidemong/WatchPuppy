from __future__ import annotations

import argparse
from app.main import main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dog Rise Alert CLI")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    return parser


def cli() -> None:
    args = build_parser().parse_args()
    main(args.config)


if __name__ == "__main__":
    cli()
