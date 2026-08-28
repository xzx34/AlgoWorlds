"""Final-decision checker for Machine Layout."""

from __future__ import annotations

from typing import Any, Mapping

from . import checker


CASE_NAME = "case_17_machine_layout"


def _payload(state: Mapping[str, Any]) -> Mapping[str, Any]:
    return state.get("payload", state)


def validate(state: Mapping[str, Any], submission: Any) -> tuple[bool, int | None]:
    assignment = submission.get("assignment") if isinstance(submission, dict) else None
    result = checker.evaluate_layout(_payload(state), assignment)
    objective = int(result.objective) if result.objective is not None else None
    return result.legal, objective
