"""Inspect the public AlgoWorlds identity roster."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from algoworlds.identity import TASK_FAMILY_BY_ID, ToolInterface, WorkloadLevel
from algoworlds.manifest import load_public_manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="algoworlds worlds",
        description="Inspect the 240 public algorithmic-world identities.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    listing = subcommands.add_parser("list", help="list algorithmic worlds")
    listing.add_argument(
        "--task-family",
        choices=tuple(TASK_FAMILY_BY_ID),
        help="include only one task family",
    )
    listing.add_argument(
        "--workload-level",
        choices=tuple(level.value for level in WorkloadLevel),
        help="include only one workload level",
    )
    listing.add_argument(
        "--instance-index",
        choices=(1, 2, 3),
        type=int,
        help="include only one hidden-instance index",
    )
    listing.add_argument(
        "--tool-interface",
        choices=tuple(interface.value for interface in ToolInterface),
        help="include only one tool interface",
    )
    listing.add_argument(
        "--json",
        action="store_true",
        help="emit a JSON array instead of one ID per line",
    )
    return parser


def _selected(args: argparse.Namespace) -> list[dict[str, str | int]]:
    records = load_public_manifest()["algorithmic_worlds"]
    filters = {
        "task_family_id": args.task_family,
        "workload_level": args.workload_level,
        "instance_index": args.instance_index,
        "tool_interface": args.tool_interface,
    }
    return [
        record
        for record in records
        if all(value is None or record[field] == value for field, value in filters.items())
    ]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    if args.command != "list":
        raise AssertionError(f"unhandled command: {args.command}")
    records = _selected(args)
    if args.json:
        print(json.dumps(records, indent=2, sort_keys=True))
    else:
        for record in records:
            print(record["algorithmic_world_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
