"""Positive-cost information API and binding submission for Case 07."""

from __future__ import annotations

from typing import Any, Callable

from algoworlds.runtime_core import CostModel, first_submission_args

from . import runtime_data
from . import world


QUERY_TOOLS = tuple(runtime_data.QUERY_COSTS)
SUBMIT_TOOL = runtime_data.SUBMIT_TOOL
COST_MODEL = CostModel(dict(runtime_data.QUERY_COSTS))


def _schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


class StationSitingAPI:
    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state
        self._spent = 0
        self._evaluated = False
        self._submitted = False
        self._trajectory: list[dict[str, Any]] = []

    @property
    def budget(self) -> int:
        return int(self._state["public"]["cost_budget"])

    @property
    def spent(self) -> int:
        return self._spent

    def trajectory(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._trajectory]

    def tool_schemas(self) -> list[dict[str, Any]]:
        handle = {"type": "string"}
        sites = {"type": "array", "items": handle}
        return [
            _schema("read_zone", "Read both candidate-site rows for one zone.", {"zone": handle}, ["zone"]),
            _schema("read_demand", "Read one physical conjunctive-demand relation and reward.", {"demand": handle}, ["demand"]),
            _schema(
                "read_zone_window",
                "Read only site economics for two or three consecutive zones; demand relations remain separate.",
                {"start": handle, "length": {"type": "integer", "enum": [2, 3]}},
                ["start", "length"],
            ),
            _schema(
                "evaluate_layout",
                "One-shot evaluation of only the exact caller-supplied complete "
                "layout; returns the objective shifted by the fixed economics-only "
                "baseline, and an illegal candidate consumes the opportunity.",
                {"sites": sites},
                ["sites"],
            ),
            _schema(SUBMIT_TOOL, "Submit one binding terminal site layout.", {"sites": sites}, ["sites"]),
        ]

    def _record(self, tool: str, args: dict[str, Any], result: dict[str, Any], cost: int) -> dict[str, Any]:
        self._trajectory.append(
            {"fn": tool, "args": dict(args), "result": result, "charged_cost": cost, "spent_after": self._spent}
        )
        return result

    def _query(self, tool: str, args: dict[str, Any], operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        if self._submitted:
            return self._record(tool, args, {"error": "round is terminal after submission"}, 0)
        cost = self._state["cost_vector"][tool]
        if self._spent + cost > self.budget:
            return self._record(tool, args, {"error": "insufficient remaining budget"}, 0)
        self._spent += cost
        try:
            result = operation()
        except (KeyError, TypeError, ValueError) as exc:
            result = {"error": str(exc)}
        return self._record(tool, args, result, cost)

    @property
    def _documents(self) -> dict[str, Any]:
        return self._state["source_documents"]

    def _zone_rows(self, zone: Any) -> list[dict[str, Any]]:
        if not isinstance(zone, str) or zone not in self._documents["zone_order"]:
            raise ValueError("unknown zone handle")
        return [dict(row) for row in self._documents["site_rows"] if row["zone_id"] == zone]

    def read_zone(self, zone: Any) -> dict[str, Any]:
        return self._query("read_zone", {"zone": zone}, lambda: {"rows": self._zone_rows(zone)})

    def read_demand(self, demand: Any) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            if not isinstance(demand, str) or demand not in self._documents["demand_order"]:
                raise ValueError("unknown demand handle")
            return runtime_data._demand_observation(self._documents, demand)

        return self._query("read_demand", {"demand": demand}, operation)

    def read_zone_window(self, start: Any, length: Any) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            if isinstance(length, bool) or not isinstance(length, int) or length not in (2, 3):
                raise ValueError("window length must be two or three")
            if not isinstance(start, str) or start not in self._documents["zone_order"]:
                raise ValueError("unknown start zone")
            index = self._documents["zone_order"].index(start)
            if index + length > len(self._documents["zone_order"]):
                raise ValueError("window exceeds the zone order")
            zone_records = []
            for position in range(index, index + length):
                zone_records.extend(self._zone_rows(self._documents["zone_order"][position]))
            return {"site_rows": zone_records}

        return self._query("read_zone_window", {"start": start, "length": length}, operation)

    def evaluate_layout(self, sites: Any) -> dict[str, Any]:
        args = {"sites": sites}
        if self._evaluated:
            return self._record(
                "evaluate_layout", args, {"error": "already evaluated"}, 0
            )
        # Consume the sole feedback opportunity before validation.  Otherwise a
        # malformed probe could be followed by arbitrarily many scalar probes.
        self._evaluated = True

        def operation() -> dict[str, Any]:
            try:
                value = runtime_data.layout_value(self._state, sites)
            except (KeyError, TypeError, ValueError) as exc:
                return {"legal": False, "objective": None, "reason": str(exc)}
            return {"legal": True, "objective": value, "reason": None}

        return self._query("evaluate_layout", args, operation)

    def submit_sites(self, sites: Any) -> dict[str, Any]:
        args = {"sites": sites}
        if self._submitted:
            return self._record(SUBMIT_TOOL, args, {"error": "already submitted"}, 0)
        self._submitted = True
        legal, value = world.validate(self._state, {"sites": sites})
        return self._record(
            SUBMIT_TOOL,
            args,
            {"submitted": True, "legal": legal, "objective": value},
            0,
        )


def dispatch(api: StationSitingAPI, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool not in (*QUERY_TOOLS, SUBMIT_TOOL):
        raise ValueError(f"unknown tool: {tool!r}")
    return getattr(api, tool)(**args)


def extract_submission(trajectory: list[dict[str, Any]]) -> dict[str, Any] | None:
    args = first_submission_args(trajectory, SUBMIT_TOOL)
    if args is None or not isinstance(args.get("sites"), list):
        return None
    return {"sites": args["sites"]}
