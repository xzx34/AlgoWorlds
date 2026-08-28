"""Public command router for AlgoWorlds."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from algoworlds._delegate import delegate


_HELP = """\
usage: algoworlds <command> [arguments]

Commands:
  worlds list      List public algorithmic-world identities.
  evaluate         Evaluate one model with a provider-neutral profile.
  score            Score one complete trial by Exact optimality.
  release verify   Verify the bundled benchmark artifacts.

Run `algoworlds <command> --help` for command-specific arguments.
"""


def _usage_error(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    print(_HELP, file=sys.stderr, end="")
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    """Route one stable public command."""

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args == ["--help"] or args == ["-h"]:
        print(_HELP, end="")
        return 0
    if args == ["--version"]:
        from algoworlds import __version__

        print(__version__)
        return 0

    command = args.pop(0)
    if command == "worlds":
        return delegate("algoworlds.worlds", args)
    if command == "evaluate":
        return delegate("algoworlds.evaluate", args)
    if command == "score":
        return delegate("algoworlds.score", args)
    if command == "release":
        return delegate("algoworlds.release", args)
    return _usage_error(f"unknown command {command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
