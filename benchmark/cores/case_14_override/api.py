"""Costed discovery and binding submission API for canonical Case 14."""

from __future__ import annotations

from typing import Any

from benchmark.cores.case_14_override import runtime_data
from benchmark.cores.case_14_override import world
from algoworlds.runtime_core import CostModel, first_submission_args


QUERY_TOOLS = tuple(runtime_data.QUERY_COSTS)
SUBMIT_TOOL = "submit_package"
COST_MODEL = CostModel(dict(runtime_data.QUERY_COSTS))


def catalog_observation(documents: dict[str, Any], stages: set[str]) -> dict[str, Any]:
    grouped = []
    for stage in documents["stage_order"]:
        if stage not in stages:
            continue
        rows = sorted(
            (
                [
                    row["play_id"],
                    row["base_cost"],
                    row["override_code"],
                    row["clearance_residue"],
                ]
                for row in documents["catalog"]
                if row["stage_id"] == stage
            ),
            key=lambda row: row[0],
        )
        grouped.append({"stage_id": stage, "rows": rows})
    return {
        "columns": [
            "play_id",
            "base_cost",
            "override_code",
            "clearance_residue",
        ],
        "stages": grouped,
    }


def authorization_observation(
    documents: dict[str, Any], stages: set[str]
) -> dict[str, Any]:
    authorization = documents["authorization"]
    grouped = []
    if authorization["encoding"] == "direct":
        for stage in documents["stage_order"]:
            if stage not in stages:
                continue
            rows = sorted(
                (
                    [row["predecessor_id"], row["successor_id"], row["handoff_cost"]]
                    for row in authorization["rows"]
                    if row["stage_id"] == stage
                ),
                key=lambda row: (row[0], row[1]),
            )
            grouped.append({"stage_id": stage, "rows": rows})
        return {"encoding": "direct", "stages": grouped}

    for stage in documents["stage_order"]:
        if stage not in stages:
            continue
        entries = [
            row
            for row in authorization["authorization_entries"]
            if row["stage_id"] == stage
        ]
        exits = [
            row
            for row in authorization["authorization_exits"]
            if row["stage_id"] == stage
        ]
        approvals = sorted(row["approval_id"] for row in entries)
        slot = {approval: index for index, approval in enumerate(approvals)}
        entry_rows = sorted(
            ([row["predecessor_id"], slot[row["approval_id"]]] for row in entries),
            key=lambda row: (row[0], row[1]),
        )
        exit_rows = sorted(
            (
                [slot[row["approval_id"]], row["successor_id"], row["handoff_cost"]]
                for row in exits
            ),
            key=lambda row: (row[0], row[1]),
        )
        grouped.append(
            {"stage_id": stage, "authorization_entries": entry_rows, "authorization_exits": exit_rows}
        )
    return {"encoding": "staged", "stages": grouped}


def policy_observation(documents: dict[str, Any]) -> dict[str, Any]:
    return {
        "checksum": dict(documents["checksum"]),
        "columns": ["override_code", "cost_adjustment"],
        "rows": sorted(
            ([row["override_code"], row["cost_adjustment"]] for row in documents["override_policy"]),
            key=lambda row: row[0],
        ),
    }


def _function(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
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


class OverrideAPI:
    def __init__(self, world_state: dict[str, Any]) -> None:
        self._state = world_state
        self._trajectory: list[dict[str, Any]] = []
        self._evaluated = False
        self._submitted = False

    def tool_schemas(self) -> list[dict[str, Any]]:
        stage = {"stage": {"type": "string"}}
        window = {
            "start": {"type": "integer", "minimum": 0},
            "length": {"type": "integer", "enum": [2, 3]},
        }
        plays = {"plays": {"type": "array", "items": {"type": "string"}}}
        return [
            _function(
                "read_catalog_stage",
                "Read a compact play/base-cost/override-code/clearance-residue table for one stage.",
                stage,
                ["stage"],
            ),
            _function(
                "read_authorization_stage",
                "Read compact predecessor/successor/handoff-cost authorization records entering one stage.",
                stage,
                ["stage"],
            ),
            _function(
                "read_catalog_window",
                "Read compact catalog tables for two or three consecutive stages.",
                window,
                ["start", "length"],
            ),
            _function(
                "read_authorization_window",
                "Read compact authorization and handoff-cost tables for two or three consecutive stages.",
                window,
                ["start", "length"],
            ),
            _function(
                "read_override_policy",
                "Read override costs and the global clearance checksum rule without play identifiers.",
                {},
                [],
            ),
            _function(
                "evaluate_package",
                "One-shot check and price of one caller-supplied complete package; malformed or illegal input consumes the opportunity, with no recommendation or repair.",
                plays,
                ["plays"],
            ),
            _function(
                SUBMIT_TOOL,
                "Submit one complete package. This is binding and one-shot.",
                plays,
                ["plays"],
            ),
        ]

    @property
    def _documents(self) -> dict[str, Any]:
        return self._state["source_documents"]

    def _record(self, tool: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        self._trajectory.append({"fn": tool, "args": args, "result": result})
        return result

    def _known_stage(self, stage: str) -> None:
        if stage not in self._documents["stage_order"]:
            raise ValueError("unknown stage")

    def _window_stages(self, start: int, length: int) -> set[str]:
        if isinstance(start, bool) or not isinstance(start, int):
            raise ValueError("start must be an integer")
        if (
            length not in (2, 3)
            or start < 0
            or start + length > len(self._documents["stage_order"])
        ):
            raise ValueError("window must be an in-range length-two/three interval")
        return set(self._documents["stage_order"][start : start + length])

    def _authorization_rows(self, stages: set[str]) -> dict[str, Any]:
        return authorization_observation(self._documents, stages)

    def read_catalog_stage(self, stage: str) -> dict[str, Any]:
        self._known_stage(stage)
        return self._record(
            "read_catalog_stage", {"stage": stage}, catalog_observation(self._documents, {stage})
        )

    def read_authorization_stage(self, stage: str) -> dict[str, Any]:
        self._known_stage(stage)
        return self._record(
            "read_authorization_stage",
            {"stage": stage},
            self._authorization_rows({stage}),
        )

    def read_catalog_window(self, start: int, length: int) -> dict[str, Any]:
        stages = self._window_stages(start, length)
        return self._record(
            "read_catalog_window",
            {"start": start, "length": length},
            catalog_observation(self._documents, stages),
        )

    def read_authorization_window(self, start: int, length: int) -> dict[str, Any]:
        stages = self._window_stages(start, length)
        return self._record(
            "read_authorization_window",
            {"start": start, "length": length},
            self._authorization_rows(stages),
        )

    def read_override_policy(self) -> dict[str, Any]:
        return self._record(
            "read_override_policy", {}, policy_observation(self._documents)
        )

    def evaluate_package(self, plays: list[str]) -> dict[str, Any]:
        if self._evaluated:
            return self._record(
                "evaluate_package", {"plays": plays}, {"error": "already evaluated"}
            )
        self._evaluated = True
        try:
            breakdown = runtime_data.package_breakdown(self._documents, plays)
        except (KeyError, TypeError, ValueError):
            result = {"complete": False, "legal": False}
        else:
            result = {
                "complete": True,
                "legal": True,
                "base_cost": breakdown["base_cost"],
                "override_adjustment": breakdown["override_adjustment"],
                "authorization_cost": breakdown["authorization_cost"],
                "total_cost": breakdown["total_cost"],
            }
        return self._record("evaluate_package", {"plays": plays}, result)

    def submit_package(self, plays: list[str]) -> dict[str, Any]:
        if self._submitted:
            return self._record(SUBMIT_TOOL, {"plays": plays}, {"error": "already submitted"})
        self._submitted = True
        legal, value = world.validate(self._state, {"plays": plays})
        return self._record(
            SUBMIT_TOOL,
            {"plays": plays},
            {"accepted": True, "legal": legal, "total_cost": value},
        )

    def trajectory(self) -> list[dict[str, Any]]:
        return list(self._trajectory)


def dispatch(api: OverrideAPI, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool not in (*QUERY_TOOLS, SUBMIT_TOOL):
        raise ValueError(f"unknown tool: {tool!r}")
    return getattr(api, tool)(**args)


def extract_submission(trajectory: list[dict[str, Any]]) -> dict[str, Any] | None:
    args = first_submission_args(trajectory, SUBMIT_TOOL)
    if args is None or not isinstance(args.get("plays"), list):
        return None
    return {"plays": args["plays"]}
