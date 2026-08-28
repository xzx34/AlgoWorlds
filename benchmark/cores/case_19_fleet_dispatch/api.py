"""Positive-cost primitive evidence API and binding dispatch submission."""

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


class FleetDispatchAPI:
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

    @property
    def _documents(self) -> dict[str, Any]:
        return self._state["source_documents"]

    def trajectory(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._trajectory]

    def tool_schemas(self) -> list[dict[str, Any]]:
        handle = {"type": "string"}
        assignment = {"type": "object", "additionalProperties": handle}
        return [
            _schema("read_fleet_policy", "Read vehicle capacities and the complete vehicle/job rosters.", {}, []),
            _schema("read_job", "Read one job load and its eligible vehicles, without route costs.", {"job": handle}, ["job"]),
            _schema(
                "read_vehicle_contract",
                "Read one vehicle's fixed activation price; capacities come only from fleet policy.",
                {"vehicle": handle},
                ["vehicle"],
            ),
            _schema("read_route_row", "Read one vehicle's direct or mediated primitive route-cost row.", {"vehicle": handle}, ["vehicle"]),
            _schema(
                "read_dispatch_window",
                "Read loads and primitive route records for two or three consecutive jobs.",
                {"start": handle, "length": {"type": "integer", "enum": [2, 3]}},
                ["start", "length"],
            ),
            _schema(
                "evaluate_assignment",
                "Evaluate only the caller-supplied map under the public lower-bound-normalized objective.",
                {"assignment": assignment},
                ["assignment"],
            ),
            _schema(SUBMIT_TOOL, "Submit one binding terminal job-to-vehicle assignment.", {"assignment": assignment}, ["assignment"]),
        ]

    def _record(self, tool: str, args: dict[str, Any], result: dict[str, Any], cost: int) -> dict[str, Any]:
        self._trajectory.append(
            {"fn": tool, "args": dict(args), "result": result, "charged_cost": cost, "spent_after": self._spent}
        )
        return result

    def _query(self, tool: str, args: dict[str, Any], operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        if self._submitted:
            return self._record(tool, args, {"error": "round is terminal after submission"}, 0)
        cost = self._state.get("cost_vector", runtime_data.QUERY_COSTS)[tool]
        if self._spent + cost > self.budget:
            return self._record(tool, args, {"error": "insufficient remaining budget"}, 0)
        self._spent += cost
        try:
            result = operation()
        except (KeyError, TypeError, ValueError) as exc:
            result = {"error": str(exc)}
        return self._record(tool, args, result, cost)

    def read_fleet_policy(self) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            contracts = runtime_data.contract_index(self._documents)
            return {
                "vehicles": [
                    {"vehicle_id": vehicle, "capacity": contracts[vehicle]["capacity"]}
                    for vehicle in self._documents["vehicle_order"]
                ],
                "jobs": list(self._documents["job_order"]),
            }

        return self._query("read_fleet_policy", {}, operation)

    def read_job(self, job: Any) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            if not isinstance(job, str) or job not in self._documents["job_order"]:
                raise ValueError("unknown job handle")
            row = runtime_data.job_index(self._documents)[job]
            routes = runtime_data.normalized_routes(self._documents)
            return {
                "job_id": job,
                "load": row["load"],
                "eligible_vehicles": [
                    vehicle for vehicle in self._documents["vehicle_order"] if (vehicle, job) in routes
                ],
            }

        return self._query("read_job", {"job": job}, operation)

    def read_vehicle_contract(self, vehicle: Any) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            contracts = runtime_data.contract_index(self._documents)
            if not isinstance(vehicle, str) or vehicle not in contracts:
                raise ValueError("unknown vehicle handle")
            row = contracts[vehicle]
            return {
                "vehicle_id": vehicle,
                "fixed_contract_cost": row["fixed_contract_cost"],
            }

        return self._query("read_vehicle_contract", {"vehicle": vehicle}, operation)

    def read_route_row(self, vehicle: Any) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            if not isinstance(vehicle, str) or vehicle not in self._documents["vehicle_order"]:
                raise ValueError("unknown vehicle handle")
            return runtime_data._route_row_observation(self._documents, vehicle)

        return self._query("read_route_row", {"vehicle": vehicle}, operation)

    def read_dispatch_window(self, start: Any, length: Any) -> dict[str, Any]:
        def operation() -> dict[str, Any]:
            if isinstance(length, bool) or not isinstance(length, int) or length not in (2, 3):
                raise ValueError("window length must be two or three")
            if not isinstance(start, str) or start not in self._documents["job_order"]:
                raise ValueError("unknown start job")
            index = self._documents["job_order"].index(start)
            if index + length > len(self._documents["job_order"]):
                raise ValueError("window exceeds the job order")
            jobs = self._documents["job_order"][index : index + length]
            job_rows = runtime_data.job_index(self._documents)
            return {
                "job_rows": [job_rows[job] for job in jobs],
                "route_records": runtime_data._job_route_observations(self._documents, set(jobs)),
            }

        return self._query("read_dispatch_window", {"start": start, "length": length}, operation)

    def evaluate_assignment(self, assignment: Any) -> dict[str, Any]:
        if self._evaluated:
            return self._record(
                "evaluate_assignment",
                {"assignment": assignment},
                {"error": "already evaluated"},
                0,
            )
        # Candidate feedback is a one-shot verification aid, not an iterative
        # scalar checker.  Invalid candidates consume the opportunity as well.
        self._evaluated = True

        def operation() -> dict[str, Any]:
            try:
                value = runtime_data.assignment_value(self._state, assignment)
            except (KeyError, TypeError, ValueError) as exc:
                return {"legal": False, "total_cost": None, "reason": str(exc)}
            return {"legal": True, "total_cost": value, "reason": None}

        return self._query("evaluate_assignment", {"assignment": assignment}, operation)

    def submit_assignment(self, assignment: Any) -> dict[str, Any]:
        args = {"assignment": assignment}
        if self._submitted:
            return self._record(SUBMIT_TOOL, args, {"error": "already submitted"}, 0)
        self._submitted = True
        legal, value = world.validate(self._state, {"assignment": assignment})
        return self._record(
            SUBMIT_TOOL,
            args,
            {"submitted": True, "legal": legal, "total_cost": value},
            0,
        )


def dispatch(api: FleetDispatchAPI, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool not in (*QUERY_TOOLS, SUBMIT_TOOL):
        raise ValueError(f"unknown tool: {tool!r}")
    return getattr(api, tool)(**args)


def extract_submission(trajectory: list[dict[str, Any]]) -> dict[str, Any] | None:
    args = first_submission_args(trajectory, SUBMIT_TOOL)
    if args is None or not isinstance(args.get("assignment"), dict):
        return None
    return {"assignment": args["assignment"]}
