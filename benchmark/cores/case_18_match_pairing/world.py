"""Final-decision checker for Sequential Matching."""

from __future__ import annotations

from typing import Any

from . import runtime_data


CASE_NAME = runtime_data.CASE_ID


def validate(state: dict[str, Any], submission: Any) -> tuple[bool, int | None]:
    if not isinstance(submission, dict) or not isinstance(submission.get("pairs"), list):
        return False, None
    try:
        value = runtime_data.matching_cost(state["source_documents"], submission["pairs"])
    except (KeyError, TypeError, ValueError):
        return False, None
    return True, value
