"""Small, lazy adapters from public commands to the shared benchmark engine."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Protocol, cast


class _Entrypoint(Protocol):
    def __call__(self, argv: list[str] | None = None) -> int: ...


def delegate(module_name: str, argv: Sequence[str] | None = None) -> int:
    """Load ``module_name.main`` only when a command is actually executed.

    Keeping imports lazy lets ``algoworlds --help`` and package inspection work
    without importing provider SDKs. Both provider-facing commands use this
    function, so there is only one evaluation engine.
    """

    module = importlib.import_module(module_name)
    entrypoint = cast(_Entrypoint, getattr(module, "main"))
    args = None if argv is None else list(argv)
    return int(entrypoint(args))
