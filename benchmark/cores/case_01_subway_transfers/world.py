"""Final-decision checker for Transit Routing."""

from __future__ import annotations

from typing import Any, Mapping

from . import checker


def _payload(world_state: Mapping[str, Any]) -> Mapping[str, Any]:
    return world_state.get("payload", world_state)


def validate(world_state: Mapping[str, Any], submission: Any) -> tuple[bool, int | None]:
    payload = _payload(world_state)
    legs = submission.get("legs") if isinstance(submission, dict) else None
    result = checker.evaluate_route(payload, legs)
    objective = int(result.objective) if result.objective is not None else None
    return result.legal, objective
