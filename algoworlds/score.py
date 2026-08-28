"""Command-line entry point for official Exact-optimality scoring."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from algoworlds.manifest import DEFAULT_MANIFEST_PATH, ManifestError
from algoworlds.scoring import ScoringError, load_submissions, score_trial


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="algoworlds score",
        description="Score one complete 240-world trial by Exact optimality.",
    )
    parser.add_argument("submissions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    try:
        result = score_trial(
            load_submissions(args.submissions), manifest_path=args.manifest
        )
    except (ManifestError, ScoringError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"Exact optimality: {result['exact_optimal_count']}/"
        f"{result['world_count']} ({result['exact_optimality_percent']:.6g}%)"
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
