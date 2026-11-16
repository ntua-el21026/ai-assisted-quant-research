"""Canonical credential-free offline research command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from packages.research.runner import run_research


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline R1 research; explicit local inputs only")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--dataset", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        summary = run_research(args.config, args.dataset, args.output)
    except (OSError, ValueError) as exc:
        print(f"research_failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "run_id": summary.run_id,
                "output_dir": str(summary.output_dir),
                "deterministic_sha256": summary.deterministic_sha256,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
