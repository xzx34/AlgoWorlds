"""Costed hidden-world tools and one-shot route submission for Case 01."""

from __future__ import annotations

from typing import Any, Mapping

from benchmark.cores.case_01_subway_transfers import checker
from benchmark.cores.case_01_subway_transfers import runtime_data
from algoworlds.runtime_core import first_submission_args


QUERY_TOOLS = (
    "survey_route",
    "read_departures",
    "read_stage_memberships",
    "read_transfer_costs",
    "read_station_window",
    "evaluate_route",
)
SUBMIT_TOOL = "submit_route"


def _payload(world_state: Mapping[str, Any]) -> Mapping[str, Any]:
    return world_state.get("payload", world_state)


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


def survey_route(payload: Mapping[str, Any]) -> dict[str, Any]:
    stations = [
        row["station_id"]
        for row in sorted(payload["stations"], key=lambda row: row["order"])
    ]
    return {
        "source": stations[0],
        "destination": stations[-1],
        "ordered_stations": stations,
        "line_ids": list(runtime_data.line_order(payload)),
        "route_depth": payload["depth"],
        "checksum_modulus": payload["checksum_modulus"],
        "required_ticket_residue": payload["required_ticket_residue"],
    }


def read_departures(payload: Mapping[str, Any], station_id: str) -> dict[str, Any]:
    rows = [
        [row["leg_id"], row["travel_time"], row["ticket_residue"]]
        for row in payload["legs"]
        if row["from_station"] == station_id
    ]
    if not rows:
        return {"error": "unknown departure station"}
    full_row = next(row for row in payload["legs"] if row["from_station"] == station_id)
    return {
        "station_id": station_id,
        "to_station": full_row["to_station"],
        "departure_columns": ["leg_id", "travel_time", "ticket_residue"],
        "departures": sorted(rows, key=lambda row: row[0]),
    }


def stage_memberships(payload: Mapping[str, Any], station_id: str) -> dict[str, Any]:
    stations = sorted(payload["stations"], key=lambda row: row["order"])
    stage_by_station = {
        row["station_id"]: row["order"]
        for row in stations
        if row["order"] < payload["depth"]
    }
    if not isinstance(station_id, str) or station_id not in stage_by_station:
        return {"error": "unknown departure station"}
    stage_index = stage_by_station[station_id]
    contracted = runtime_data.relation_by_leg(payload)
    rows = runtime_data.legs_by_stage(payload)[stage_index]
    relation = payload["relation"]
    if relation["encoding"] == "direct":
        result = {
            "station_id": station_id,
            "representation": "direct_leg_line",
            "row_columns": ["leg_id", "line_id"],
            "rows": sorted(
                [
                    [row["leg_id"], contracted[row["leg_id"]]["line_id"]]
                    for row in rows
                ],
                key=lambda row: row[0],
            ),
        }
    else:
        physical = {row["leg_id"]: row for row in relation["leg_platforms"]}
        platform_ids = sorted(
            physical[row["leg_id"]]["from_platform"] for row in rows
        )
        slot_by_platform = {
            platform_id: slot for slot, platform_id in enumerate(platform_ids)
        }
        leg_platform_rows = [
            [
                row["leg_id"],
                slot_by_platform[physical[row["leg_id"]]["from_platform"]],
            ]
            for row in rows
        ]
        platform_line_rows = [
            [
                slot_by_platform[physical[row["leg_id"]]["from_platform"]],
                contracted[row["leg_id"]]["line_id"],
            ]
            for row in rows
        ]
        result = {
            "station_id": station_id,
            "representation": "leg_platform_line",
            "leg_platform_columns": ["leg_id", "platform_slot"],
            "leg_platform_rows": sorted(leg_platform_rows, key=lambda row: row[0]),
            "platform_line_columns": ["platform_slot", "line_id"],
            "platform_line_rows": sorted(platform_line_rows, key=lambda row: row[0]),
        }
    return result


def transfer_costs(payload: Mapping[str, Any], line_id: str) -> dict[str, Any]:
    lines = runtime_data.line_order(payload)
    if line_id not in lines:
        return {"error": "unknown line"}
    matrix = runtime_data.transfer_cost_index(payload)
    return {
        "from_line_id": line_id,
        "column_order": "survey_line_ids",
        "costs": [matrix[line_id, destination] for destination in lines],
    }


def station_window(
    payload: Mapping[str, Any], start_station_id: str, span: int
) -> dict[str, Any]:
    if type(span) is not int or span not in (2, 3):
        return {"error": "span must be 2 or 3"}
    stations = sorted(payload["stations"], key=lambda row: row["order"])
    start_by_station = {
        row["station_id"]: row["order"]
        for row in stations
        if row["order"] < payload["depth"]
    }
    if not isinstance(start_station_id, str) or start_station_id not in start_by_station:
        return {"error": "unknown start station"}
    start_index = start_by_station[start_station_id]
    if start_index < 0 or start_index + span > payload["depth"]:
        return {"error": "window is outside the route"}
    stage_results = []
    for stage_rows in runtime_data.legs_by_stage(payload)[start_index : start_index + span]:
        first = stage_rows[0]
        stage_results.append(
            {
                "from_station": first["from_station"],
                "to_station": first["to_station"],
                "departure_columns": ["leg_id", "travel_time", "ticket_residue"],
                "departures": [
                    [row["leg_id"], row["travel_time"], row["ticket_residue"]]
                    for row in stage_rows
                ],
            }
        )
    return {
        "start_station_id": start_station_id,
        "span": span,
        "stages": stage_results,
    }


def evaluate_candidate(payload: Mapping[str, Any], legs: Any) -> dict[str, Any]:
    evaluation = checker.evaluate_route(payload, legs)
    if not evaluation.legal:
        return {"legal": False}
    return {"legal": True, **checker.route_breakdown(payload, legs)}


class SubwayAPI:
    def __init__(self, world_state: Mapping[str, Any]) -> None:
        self._payload = _payload(world_state)
        self._trajectory: list[dict[str, Any]] = []
        self._evaluated = False
        self._submitted = False

    def tool_schemas(self) -> list[dict[str, Any]]:
        leg_array = {"type": "array", "items": {"type": "string"}}
        return [
            _function(
                "survey_route",
                "Read the ordered station chain, opaque line directory, and the public ticket-checksum rule.",
                {},
                [],
            ),
            _function(
                "read_departures",
                "Read outgoing legs, travel times, and ticket residues at one known station.",
                {"station_id": {"type": "string"}},
                ["station_id"],
            ),
            _function(
                "read_stage_memberships",
                "Read every arm-specific leg-to-line membership leaving one surveyed station.",
                {"station_id": {"type": "string"}},
                ["station_id"],
            ),
            _function(
                "read_transfer_costs",
                "Read the complete directed transfer-price row leaving one known line.",
                {"line_id": {"type": "string"}},
                ["line_id"],
            ),
            _function(
                "read_station_window",
                "Read topology, travel times, and ticket residues in a two- or three-stage window; memberships and transfer prices remain separate.",
                {
                    "start_station_id": {"type": "string"},
                    "span": {"type": "integer", "enum": [2, 3]},
                },
                ["start_station_id", "span"],
            ),
            _function(
                "evaluate_route",
                "Settle one caller-supplied complete route without submitting it; this expensive call reveals no source rows or optimality gap.",
                {"legs": leg_array},
                ["legs"],
            ),
            _function(
                "submit_route",
                "Irreversibly submit one complete ordered route.",
                {"legs": leg_array},
                ["legs"],
            ),
        ]

    def _record(
        self, tool: str, args: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        self._trajectory.append({"fn": tool, "args": args, "result": result})
        return result

    def survey_route(self) -> dict[str, Any]:
        return self._record("survey_route", {}, survey_route(self._payload))

    def read_departures(self, station_id: str) -> dict[str, Any]:
        return self._record(
            "read_departures",
            {"station_id": station_id},
            read_departures(self._payload, station_id),
        )

    def read_stage_memberships(self, station_id: str) -> dict[str, Any]:
        return self._record(
            "read_stage_memberships",
            {"station_id": station_id},
            stage_memberships(self._payload, station_id),
        )

    def read_transfer_costs(self, line_id: str) -> dict[str, Any]:
        return self._record(
            "read_transfer_costs",
            {"line_id": line_id},
            transfer_costs(self._payload, line_id),
        )

    def read_station_window(self, start_station_id: str, span: int) -> dict[str, Any]:
        return self._record(
            "read_station_window",
            {"start_station_id": start_station_id, "span": span},
            station_window(self._payload, start_station_id, span),
        )

    def evaluate_route(self, legs: Any) -> dict[str, Any]:
        if self._evaluated:
            return self._record(
                "evaluate_route", {"legs": legs}, {"error": "already evaluated"}
            )
        # Consume the sole verification opportunity before validating the
        # candidate.  Otherwise malformed probes could be retried as a
        # black-box search checker.
        self._evaluated = True
        return self._record(
            "evaluate_route", {"legs": legs}, evaluate_candidate(self._payload, legs)
        )

    def submit_route(self, legs: Any) -> dict[str, Any]:
        if self._submitted:
            return self._record(
                "submit_route", {"legs": legs}, {"error": "already submitted"}
            )
        self._submitted = True
        evaluation = checker.evaluate_route(self._payload, legs)
        return self._record(
            "submit_route",
            {"legs": legs},
            {
                "accepted": True,
                "legal": evaluation.legal,
                "encoded_cost": evaluation.objective,
            },
        )

    def trajectory(self) -> list[dict[str, Any]]:
        return list(self._trajectory)


def dispatch(api: SubwayAPI, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool not in (*QUERY_TOOLS, SUBMIT_TOOL):
        raise ValueError(f"unknown tool: {tool!r}")
    return getattr(api, tool)(**args)


def extract_submission(trajectory: list[dict[str, Any]]) -> dict[str, Any] | None:
    args = first_submission_args(trajectory, SUBMIT_TOOL)
    if args is None or not isinstance(args.get("legs"), list):
        return None
    return {"legs": args["legs"]}
