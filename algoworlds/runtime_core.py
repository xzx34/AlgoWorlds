"""Small runtime primitives shared by the curated benchmark interfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CostModel:
    """Integer query costs for one frozen algorithmic world."""

    costs: Mapping[str, int] = field(default_factory=dict)
    default_cost: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.default_cost, bool) or self.default_cost < 1:
            raise ValueError("default_cost must be a positive integer")
        for tool, cost in self.costs.items():
            if not isinstance(tool, str) or not tool:
                raise ValueError("tool names must be nonempty strings")
            if isinstance(cost, bool) or not isinstance(cost, int) or cost < 1:
                raise ValueError(f"cost for {tool!r} must be a positive integer")

    def cost_of(self, tool: str) -> int:
        return self.costs.get(tool, self.default_cost)


def binding_submission_index(
    trajectory: Sequence[Mapping[str, Any]], submit_tool: str
) -> int | None:
    """Return the first successfully executed terminal-tool call."""

    for index, entry in enumerate(trajectory):
        if not isinstance(entry, Mapping) or entry.get("fn") != submit_tool:
            continue
        result = entry.get("result")
        if isinstance(result, Mapping) and result.get("error"):
            continue
        return index
    return None


def first_submission_args(
    trajectory: Sequence[Mapping[str, Any]], submit_tool: str
) -> dict[str, Any] | None:
    """Return arguments from the first successfully executed terminal tool."""

    index = binding_submission_index(trajectory, submit_tool)
    if index is None:
        return None
    args = trajectory[index].get("args", {})
    return dict(args) if isinstance(args, Mapping) else {}


def affordable_query_tools(
    query_tools: Sequence[str], cost_model: CostModel, remaining_cost: int
) -> tuple[str, ...]:
    return tuple(
        tool
        for tool in sorted(query_tools)
        if cost_model.cost_of(tool) <= remaining_cost
    )


def budget_exhausted_result(max_cost: int, spent_cost: int) -> dict[str, Any]:
    return {
        "error": "query budget exhausted",
        "budget_exhausted": True,
        "max_cost": max_cost,
        "spent_cost": spent_cost,
    }


def budget_rejection_result(
    max_cost: int,
    spent_cost: int,
    attempted_tool: str,
    query_tools: Sequence[str],
    cost_model: CostModel,
) -> dict[str, Any]:
    """Return the standard result for an unaffordable query."""

    remaining_cost = max_cost - spent_cost
    affordable = affordable_query_tools(query_tools, cost_model, remaining_cost)
    if not affordable:
        return budget_exhausted_result(max_cost, spent_cost)
    return {
        "error": "query would exceed the remaining cost budget",
        "query_rejected": True,
        "budget_exhausted": False,
        "attempted_tool": attempted_tool,
        "attempted_cost": cost_model.cost_of(attempted_tool),
        "max_cost": max_cost,
        "spent_cost": spent_cost,
        "remaining_cost": remaining_cost,
        "affordable_query_tools": list(affordable),
    }


def render_tool_costs(cost_model: CostModel, tools: Sequence[str]) -> str:
    """Render the compact tool-cost text used by the frozen prompts."""

    return ", ".join(
        f"{tool}={cost_model.cost_of(tool)}" for tool in sorted(tools)
    )


__all__ = (
    "CostModel",
    "affordable_query_tools",
    "binding_submission_index",
    "budget_exhausted_result",
    "budget_rejection_result",
    "first_submission_args",
    "render_tool_costs",
)
