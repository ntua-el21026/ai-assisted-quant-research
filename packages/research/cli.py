"""Canonical credential-free offline research command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from packages.research.runner import evaluate_research, run_research


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline registered research; explicit local inputs only"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "evaluate"):
        command = commands.add_parser(name)
        command.add_argument("--config", required=True, type=Path)
        command.add_argument("--dataset", required=True, type=Path)
        command.add_argument("--output", required=True, type=Path)
        if name == "evaluate":
            command.add_argument(
                "--include-final",
                action="store_true",
                help="Execute the separately registered final evaluation without tuning",
            )
    args = parser.parse_args(argv)
    try:
        summary = (
            run_research(args.config, args.dataset, args.output)
            if args.command == "run"
            else evaluate_research(
                args.config, args.dataset, args.output, include_final=args.include_final
            )
        )
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
