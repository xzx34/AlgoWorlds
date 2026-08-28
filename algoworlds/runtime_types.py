"""Small runtime contracts used by the curated AlgoWorlds release."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Evaluation:
    """Result of checking one family-specific final decision."""

    legal: bool
    objective: int | None


@dataclass(frozen=True)
class QueryCall:
    """One deterministic query used by model-facing observation helpers."""

    call_id: str
    tool: str
    args: Mapping[str, Any]


__all__ = ("Evaluation", "QueryCall")
