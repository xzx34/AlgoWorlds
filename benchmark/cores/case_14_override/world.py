"""Final-decision checker for Authorization Planning."""

from __future__ import annotations

from typing import Any

from . import runtime_data


CASE_NAME = runtime_data.CASE_ID


def validate(state: dict[str, Any], submission: Any) -> tuple[bool, int | None]:
    if not isinstance(submission, dict) or not isinstance(submission.get("plays"), list):
        return False, None
    try:
        result = runtime_data.package_breakdown(
            state["source_documents"], submission["plays"]
        )
    except (KeyError, TypeError, ValueError):
        return False, None
    return True, result["total_cost"]
