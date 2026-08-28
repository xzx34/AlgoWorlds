"""Final-decision checker for Station Siting."""

from __future__ import annotations

from typing import Any

from . import runtime_data


CASE_NAME = runtime_data.CASE_ID


def validate(state: dict[str, Any], submission: Any) -> tuple[bool, int | None]:
    if not isinstance(submission, dict) or not isinstance(submission.get("sites"), list):
        return False, None
    try:
        return True, runtime_data.layout_value(state, submission["sites"])
    except (KeyError, TypeError, ValueError):
        return False, None
