"""Final-decision checker for Fleet Dispatch."""

from __future__ import annotations

from typing import Any

from . import runtime_data


CASE_NAME = runtime_data.CASE_ID


def validate(state: dict[str, Any], submission: Any) -> tuple[bool, int | None]:
    if not isinstance(submission, dict) or not isinstance(submission.get("assignment"), dict):
        return False, None
    try:
        return True, runtime_data.assignment_value(state, submission["assignment"])
    except (KeyError, TypeError, ValueError):
        return False, None
