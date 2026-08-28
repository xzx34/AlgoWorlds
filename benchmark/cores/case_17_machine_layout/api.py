"""Costed primitive-coefficient tools and binding submission for Case 17."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from benchmark.cores.case_17_machine_layout import checker
from benchmark.cores.case_17_machine_layout import runtime_data
from algoworlds.runtime_core import (
    CostModel,
    budget_exhausted_result,
    first_submission_args,
)


QUERY_TOOLS = tuple(runtime_data.QUERY_COSTS)
SUBMIT_TOOL = runtime_data.SUBMIT_TOOL
COST_MODEL = CostModel(dict(runtime_data.QUERY_COSTS))


def _payload(state: Mapping[str, Any]) -> Mapping[str, Any]:
    return state.get("payload", state)


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
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


def survey_floor(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "machines": [row["machine_id"] for row in payload["machines"]],
        "slots": [row["slot_id"] for row in payload["slots"]],
        "machine_count": payload["machine_count"],
    }


def flow_row(payload: Mapping[str, Any], machine_id: str) -> dict[str, Any]:
    machines = [row["machine_id"] for row in payload["machines"]]
    if machine_id not in machines:
        return {"error": "unknown machine"}
    lookup = runtime_data.flow_lookup(payload)
    return {
        "machine_id": machine_id,
        "throughput": {
            other: lookup.get(tuple(sorted((machine_id, other))), 0)
            for other in machines
            if other != machine_id
        },
    }


def distance_row(payload: Mapping[str, Any], slot_id: str) -> dict[str, Any]:
    slots = [row["slot_id"] for row in payload["slots"]]
    if slot_id not in slots:
        return {"error": "unknown slot"}
    lookup = runtime_data.distance_lookup(payload)
    return {
        "slot_id": slot_id,
        "distance": {
            other: lookup[tuple(sorted((slot_id, other)))]
            for other in slots
            if other != slot_id
        },
    }


def settlement_row(payload: Mapping[str, Any], machine_id: str) -> dict[str, Any]:
    machines = [row["machine_id"] for row in payload["machines"]]
    if machine_id not in machines:
        return {"error": "unknown machine"}
    relation = payload["settlement"]
    if relation["encoding"] == "direct":
        records = [
            {"slot_id": row["slot_id"], "adjustment": row["adjustment"]}
            for row in relation["machine_slots"]
            if row["machine_id"] == machine_id
        ]
        return {
            "machine_id": machine_id,
            "representation": "direct_machine_slot",
            "placements": sorted(records, key=lambda row: row["slot_id"]),
        }
    anchor_slot = {row["anchor_id"]: row["slot_id"] for row in relation["anchors"]}
    cell_detail = {
        row["cell_id"]: (row["anchor_id"], anchor_slot[row["anchor_id"]])
        for row in relation["cells"]
    }
    records = []
    for row in relation["machine_cells"]:
        if row["machine_id"] != machine_id:
            continue
        anchor, slot = cell_detail[row["cell_id"]]
        records.append(
            {
                "cell_id": row["cell_id"],
                "anchor_id": anchor,
                "slot_id": slot,
                "adjustment": row["adjustment"],
            }
        )
    return {
        "machine_id": machine_id,
        "representation": "machine_cell_anchor_slot",
        "placements": sorted(records, key=lambda row: row["slot_id"]),
    }


def _block_bounds(size: int, start_index: Any, span: Any) -> range:
    if isinstance(start_index, bool) or not isinstance(start_index, int):
        raise ValueError("start_index must be an integer")
    if isinstance(span, bool) or not isinstance(span, int) or span not in (2, 3):
        raise ValueError("span must be two or three")
    if start_index < 0 or start_index + span > size:
        raise ValueError("block exceeds the surveyed roster")
    return range(start_index, start_index + span)


def flow_block(payload: Mapping[str, Any], start_index: Any, span: Any) -> dict[str, Any]:
    """Read only consecutive interaction rows; never join another channel."""

    try:
        indices = _block_bounds(len(payload["machines"]), start_index, span)
    except ValueError as exc:
        return {"error": str(exc)}
    machine_ids = [payload["machines"][index]["machine_id"] for index in indices]
    return {
        "start_index": start_index,
        "span": span,
        "flow_rows": [flow_row(payload, machine_id) for machine_id in machine_ids],
    }


def distance_block(payload: Mapping[str, Any], start_index: Any, span: Any) -> dict[str, Any]:
    """Read only consecutive geometry rows; never join another channel."""

    try:
        indices = _block_bounds(len(payload["slots"]), start_index, span)
    except ValueError as exc:
        return {"error": str(exc)}
    slot_ids = [payload["slots"][index]["slot_id"] for index in indices]
    return {
        "start_index": start_index,
        "span": span,
        "distance_rows": [distance_row(payload, slot_id) for slot_id in slot_ids],
    }


def settlement_block(
    payload: Mapping[str, Any], start_index: Any, span: Any
) -> dict[str, Any]:
    """Read only consecutive adjustment rows; never join another channel."""

    try:
        indices = _block_bounds(len(payload["machines"]), start_index, span)
    except ValueError as exc:
        return {"error": str(exc)}
    machine_ids = [payload["machines"][index]["machine_id"] for index in indices]
    return {
        "start_index": start_index,
        "span": span,
        "settlement_rows": [settlement_row(payload, machine_id) for machine_id in machine_ids],
    }


def evaluate_candidate(payload: Mapping[str, Any], assignment: Any) -> dict[str, Any]:
    evaluated = checker.evaluate_layout(payload, assignment)
    if not evaluated.legal:
        return {"legal": False}
    # Evaluation is a candidate-specific verification channel, not a shortcut
    # that decomposes or joins the three hidden coefficient channels.
    return {"legal": True, "total_cost": int(evaluated.objective)}


class MachineLayoutAPI:
    def __init__(self, state: Mapping[str, Any]) -> None:
        self._payload = _payload(state)
        self._trajectory: list[dict[str, Any]] = []
        self._spent = 0
        self._evaluated = False
        self._submitted = False

    @property
    def budget(self) -> int:
        return int(self._payload["cost_budget"])

    @property
    def spent(self) -> int:
        return self._spent

    def tool_schemas(self) -> list[dict[str, Any]]:
        string = {"type": "string"}
        assignment = {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "A complete machine-id to slot-id bijection.",
        }
        block = {
            "start_index": {
                "type": "integer",
                "minimum": 0,
                "description": "Zero-based position in the corresponding surveyed roster.",
            },
            "span": {"type": "integer", "enum": [2, 3]},
        }
        return [
            _schema("survey_floor", "Read the machine and slot rosters.", {}, []),
            _schema(
                "read_flow_row",
                "Read one machine's complete pairwise-throughput row.",
                {"machine_id": string},
                ["machine_id"],
            ),
            _schema(
                "read_distance_row",
                "Read one slot's complete pairwise-distance row.",
                {"slot_id": string},
                ["slot_id"],
            ),
            _schema(
                "read_settlement_row",
                "Read primitive placement adjustments for one machine.",
                {"machine_id": string},
                ["machine_id"],
            ),
            _schema(
                "read_flow_block",
                "Read only interaction rows for two or three consecutive surveyed machines.",
                block,
                ["start_index", "span"],
            ),
            _schema(
                "read_distance_block",
                "Read only geometry rows for two or three consecutive surveyed slots.",
                block,
                ["start_index", "span"],
            ),
            _schema(
                "read_settlement_block",
                "Read only adjustment rows for two or three consecutive surveyed machines.",
                block,
                ["start_index", "span"],
            ),
            _schema(
                "evaluate_layout",
                "Evaluate one caller-supplied complete layout without submitting it.",
                {"assignment": assignment},
                ["assignment"],
            ),
            _schema(
                SUBMIT_TOOL,
                "Irreversibly submit one complete machine layout.",
                {"assignment": assignment},
                ["assignment"],
            ),
        ]

    def _record(
        self,
        tool: str,
        args: dict[str, Any],
        result: dict[str, Any],
        charged_cost: int,
    ) -> dict[str, Any]:
        self._trajectory.append(
            {
                "fn": tool,
                "args": args,
                "result": result,
                "charged_cost": charged_cost,
                "spent_after": self._spent,
            }
        )
        return result

    def _query(
        self,
        tool: str,
        args: dict[str, Any],
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        if self._submitted:
            return self._record(
                tool, args, {"error": "round is terminal after submission"}, 0
            )
        cost = self._payload["cost_vector"][tool]
        if self._spent + cost > self.budget:
            return self._record(
                tool,
                args,
                budget_exhausted_result(self.budget, self._spent),
                0,
            )
        self._spent += cost
        try:
            result = operation()
        except (KeyError, TypeError, ValueError) as exc:
            result = {"error": str(exc)}
        return self._record(tool, args, result, cost)

    def survey_floor(self) -> dict[str, Any]:
        return self._query("survey_floor", {}, lambda: survey_floor(self._payload))

    def read_flow_row(self, machine_id: str) -> dict[str, Any]:
        return self._query(
            "read_flow_row",
            {"machine_id": machine_id},
            lambda: flow_row(self._payload, machine_id),
        )

    def read_distance_row(self, slot_id: str) -> dict[str, Any]:
        return self._query(
            "read_distance_row",
            {"slot_id": slot_id},
            lambda: distance_row(self._payload, slot_id),
        )

    def read_settlement_row(self, machine_id: str) -> dict[str, Any]:
        return self._query(
            "read_settlement_row",
            {"machine_id": machine_id},
            lambda: settlement_row(self._payload, machine_id),
        )

    def read_flow_block(self, start_index: Any, span: Any) -> dict[str, Any]:
        args = {"start_index": start_index, "span": span}
        return self._query(
            "read_flow_block", args, lambda: flow_block(self._payload, start_index, span)
        )

    def read_distance_block(self, start_index: Any, span: Any) -> dict[str, Any]:
        args = {"start_index": start_index, "span": span}
        return self._query(
            "read_distance_block",
            args,
            lambda: distance_block(self._payload, start_index, span),
        )

    def read_settlement_block(self, start_index: Any, span: Any) -> dict[str, Any]:
        args = {"start_index": start_index, "span": span}
        return self._query(
            "read_settlement_block",
            args,
            lambda: settlement_block(self._payload, start_index, span),
        )

    def evaluate_layout(self, assignment: Any) -> dict[str, Any]:
        if self._evaluated:
            return self._record(
                "evaluate_layout",
                {"assignment": assignment},
                {"error": "already evaluated"},
                0,
            )
        # An illegal candidate consumes the one feedback opportunity too.  This
        # prevents the scalar evaluator from becoming a black-box local-search
        # checker while preserving one declared verification call.
        self._evaluated = True
        return self._query(
            "evaluate_layout",
            {"assignment": assignment},
            lambda: evaluate_candidate(self._payload, assignment),
        )

    def submit_layout(self, assignment: Any) -> dict[str, Any]:
        if self._submitted:
            return self._record(
                SUBMIT_TOOL, {"assignment": assignment}, {"error": "already submitted"}, 0
            )
        self._submitted = True
        evaluated = checker.evaluate_layout(self._payload, assignment)
        return self._record(
            SUBMIT_TOOL,
            {"assignment": assignment},
            {"accepted": True, "legal": evaluated.legal, "total_cost": evaluated.objective},
            0,
        )

    def trajectory(self) -> list[dict[str, Any]]:
        return list(self._trajectory)


def dispatch(instance_api: MachineLayoutAPI, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool not in (*QUERY_TOOLS, SUBMIT_TOOL):
        raise ValueError(f"unknown tool: {tool!r}")
    return getattr(instance_api, tool)(**args)


def extract_submission(trajectory: list[dict[str, Any]]) -> dict[str, Any] | None:
    args = first_submission_args(trajectory, SUBMIT_TOOL)
    if args is None or not isinstance(args.get("assignment"), dict):
        return None
    return {"assignment": args["assignment"]}
