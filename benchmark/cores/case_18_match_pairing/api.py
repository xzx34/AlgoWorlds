"""Costed evidence API for canonical Case 18."""

from __future__ import annotations

from typing import Any

from benchmark.cores.case_18_match_pairing import runtime_data
from benchmark.cores.case_18_match_pairing import world
from benchmark.cores.case_18_match_pairing.observations import _observe
from algoworlds.runtime_types import QueryCall
from algoworlds.runtime_core import CostModel, first_submission_args


QUERY_TOOLS = tuple(runtime_data.QUERY_COSTS)
SUBMIT_TOOL = runtime_data.SUBMIT_TOOL
COST_MODEL = CostModel(dict(runtime_data.QUERY_COSTS))


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
        },
    }


class PairingAPI:
    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state
        self._trajectory: list[dict[str, Any]] = []
        self._evaluated = False
        self._submitted = False

    def tool_schemas(self) -> list[dict[str, Any]]:
        string = {"type": "string"}
        pairs = {"type": "array", "items": string}
        return [
            _schema("read_participant", "List pair handles incident to one participant. slot is its zero-based position in the published participant roster; costs are separate.", {"participant": string}, ["participant"]),
            _schema("read_pair", "Read one pair id and its cost; endpoints are separate evidence.", {"pair": string}, ["pair"]),
            _schema("read_compatibility_row", "Read compact endpoint incidence for every pair involving one participant. Participant integers index the published roster and can name later row calls; event slots are response-local; costs are omitted.", {"participant": string}, ["participant"]),
            _schema("read_pair_window", "Read one aligned compact [pair_id,cost] page. A page contains q consecutive pairs, where q is the participants-per-side value; endpoints are omitted.", {"start": {"type": "integer", "minimum": 0}, "length": {"type": "integer", "minimum": 1}}, ["start", "length"]),
            _schema("read_handoff_policy", "Read the fixed public left order, right roster, and complete directed handoff-cost table. Total cost adds the handoff from the selected right at one left position to the selected right at the next position.", {}, []),
            _schema("evaluate_matching", "Evaluate only a caller-supplied complete sequential matching; total_cost includes unary pair costs and adjacent-right handoffs under the public left order.", {"pairs": pairs}, ["pairs"]),
            _schema(SUBMIT_TOOL, "Submit a binding one-shot complete sequential matching; total_cost includes unary pair costs and adjacent-right handoffs.", {"pairs": pairs}, ["pairs"]),
        ]

    def _record(self, tool: str, args: dict, result: dict) -> dict:
        self._trajectory.append({"fn": tool, "args": args, "result": result})
        return result

    def _query(self, tool: str, args: dict) -> dict:
        result = _observe(self._state, QueryCall(f"runtime-{len(self._trajectory)}", tool, args))
        return self._record(tool, args, result)

    def read_participant(self, participant: str) -> dict:
        if participant not in self._state["source_documents"]["participant_order"]:
            raise ValueError("unknown participant")
        return self._query("read_participant", {"participant": participant})

    def read_pair(self, pair: str) -> dict:
        if pair not in self._state["source_documents"]["pair_order"]:
            raise ValueError("unknown pair")
        return self._query("read_pair", {"pair": pair})

    def read_compatibility_row(self, participant: str) -> dict:
        if participant not in self._state["source_documents"]["participant_order"]:
            raise ValueError("unknown participant")
        return self._query("read_compatibility_row", {"participant": participant})

    def read_pair_window(self, start: int, length: int) -> dict:
        size = len(self._state["source_documents"]["pair_order"])
        page_length = self._state["participants_per_side"]
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(length, bool)
            or not isinstance(length, int)
            or length != page_length
            or start < 0
            or start % page_length != 0
            or start + length > size
        ):
            raise ValueError("invalid pair window")
        return self._query("read_pair_window", {"start": start, "length": length})

    def read_handoff_policy(self) -> dict:
        return self._query("read_handoff_policy", {})

    def evaluate_matching(self, pairs: list[str]) -> dict:
        if self._evaluated:
            return self._record(
                "evaluate_matching", {"pairs": pairs}, {"error": "already evaluated"}
            )
        # Consume the opportunity before validation so malformed probes cannot
        # be used to obtain additional objective feedback.
        self._evaluated = True
        return self._query("evaluate_matching", {"pairs": pairs})

    def submit_matching(self, pairs: list[str]) -> dict:
        if self._submitted:
            return self._record(SUBMIT_TOOL, {"pairs": pairs}, {"error": "already submitted"})
        self._submitted = True
        legal, value = world.validate(self._state, {"pairs": pairs})
        return self._record(SUBMIT_TOOL, {"pairs": pairs}, {"accepted": True, "legal": legal, "total_cost": value})

    def trajectory(self) -> list[dict[str, Any]]:
        return list(self._trajectory)


def dispatch(instance_api: PairingAPI, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool not in (*QUERY_TOOLS, SUBMIT_TOOL):
        raise ValueError(f"unknown tool: {tool!r}")
    return getattr(instance_api, tool)(**args)


def extract_submission(trajectory: list[dict[str, Any]]) -> dict[str, Any] | None:
    args = first_submission_args(trajectory, SUBMIT_TOOL)
    return None if args is None or not isinstance(args.get("pairs"), list) else {"pairs": args["pairs"]}
