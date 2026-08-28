"""Final-decision checker for Basket Assembly."""

from __future__ import annotations

from typing import Any

from . import runtime_data


CASE_NAME = runtime_data.CASE_ID


def validate(state: dict[str, Any], submission: Any) -> tuple[bool, int | None]:
    if not isinstance(submission, dict) or not isinstance(submission.get("tickets"), list):
        return False, None
    try:
        value = runtime_data.basket_value(state["source_documents"], submission["tickets"])
    except (KeyError, TypeError, ValueError):
        return False, None
    return True, value
