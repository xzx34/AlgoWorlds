"""Costed evidence API for canonical Case 03."""

from __future__ import annotations

from typing import Any

from benchmark.cores.case_03_basket_assembly import runtime_data
from benchmark.cores.case_03_basket_assembly import world
from algoworlds.runtime_core import CostModel, first_submission_args


QUERY_TOOLS = runtime_data.QUERY_TOOLS
SUBMIT_TOOL = runtime_data.SUBMIT_TOOL
COST_MODEL = CostModel(dict(runtime_data.BASE_QUERY_COSTS))


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


class BasketAPI:
    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state
        self._trajectory: list[dict[str, Any]] = []
        self._evaluated = False
        self._submitted = False

    def tool_schemas(self) -> list[dict[str, Any]]:
        string = {"type": "string"}
        tickets = {"type": "array", "items": string}
        return [
            _schema("read_requirements", "Read the exact basket requirement vector.", {}, []),
            _schema("read_bundle", "Read one bundle's physical recipe without its price.", {"bundle": string}, ["bundle"]),
            _schema("read_item_index", "List bundle ids containing one public item.", {"item": string}, ["item"]),
            _schema(
                "read_catalog_window",
                "Read prices for two or three consecutive catalog records.",
                {"start": {"type": "integer", "minimum": 0}, "length": {"type": "integer", "enum": [2, 3]}},
                ["start", "length"],
            ),
            _schema(
                "evaluate_basket",
                "One-shot evaluation of only a caller-supplied ticket set; invalid input consumes the check.",
                {"tickets": tickets},
                ["tickets"],
            ),
            _schema(SUBMIT_TOOL, "Submit a binding one-shot ticket set.", {"tickets": tickets}, ["tickets"]),
        ]

    def _record(self, tool: str, args: dict, result: dict) -> dict:
        self._trajectory.append({"fn": tool, "args": args, "result": result})
        return result

    @property
    def _documents(self) -> dict:
        return self._state["source_documents"]

    def read_requirements(self) -> dict:
        return self._record("read_requirements", {}, {"rows": self._documents["requirements"]})

    def read_bundle(self, bundle: str) -> dict:
        if bundle not in self._documents["catalog_order"]:
            raise ValueError("unknown bundle")
        from benchmark.cores.case_03_basket_assembly.observations import _bundle_structure_observation

        return self._record(
            "read_bundle",
            {"bundle": bundle},
            _bundle_structure_observation(self._documents, bundle),
        )

    def read_item_index(self, item: str) -> dict:
        if item not in runtime_data.requirement_items(self._documents):
            raise ValueError("unknown item")
        bundles = runtime_data.normalized_bundles(self._documents)
        return self._record(
            "read_item_index",
            {"item": item},
            {"bundle_ids": sorted(bundle for bundle, row in bundles.items() if item in row["quantities"])},
        )

    def read_catalog_window(self, start: int, length: int) -> dict:
        if isinstance(start, bool) or not isinstance(start, int) or length not in (2, 3) or start < 0 or start + length > len(self._documents["catalog_order"]):
            raise ValueError("invalid catalog window")
        from benchmark.cores.case_03_basket_assembly.observations import _bundle_price_observation

        return self._record(
            "read_catalog_window",
            {"start": start, "length": length},
            {
                "records": [
                    _bundle_price_observation(self._documents, bundle)
                    for bundle in self._documents["catalog_order"][start : start + length]
                ]
            },
        )

    def evaluate_basket(self, tickets: list[str]) -> dict:
        if self._evaluated:
            return self._record(
                "evaluate_basket", {"tickets": tickets}, {"error": "already evaluated"}
            )
        # The one verification opportunity is consumed before validation, so
        # malformed/illegal probes cannot be retried as a black-box search.
        self._evaluated = True
        try:
            value = runtime_data.basket_value(self._documents, tickets)
        except (KeyError, TypeError, ValueError):
            result = {"complete": False, "legal": False}
        else:
            result = {"complete": True, "legal": True, "total_price": value}
        return self._record("evaluate_basket", {"tickets": tickets}, result)

    def submit_tickets(self, tickets: list[str]) -> dict:
        if self._submitted:
            return self._record(SUBMIT_TOOL, {"tickets": tickets}, {"error": "already submitted"})
        self._submitted = True
        legal, value = world.validate(self._state, {"tickets": tickets})
        return self._record(SUBMIT_TOOL, {"tickets": tickets}, {"accepted": True, "legal": legal, "total_price": value})

    def trajectory(self) -> list[dict[str, Any]]:
        return list(self._trajectory)


def dispatch(api: BasketAPI, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool not in (*QUERY_TOOLS, SUBMIT_TOOL):
        raise ValueError(f"unknown tool: {tool!r}")
    return getattr(api, tool)(**args)


def extract_submission(trajectory: list[dict[str, Any]]) -> dict[str, Any] | None:
    args = first_submission_args(trajectory, SUBMIT_TOOL)
    return None if args is None or not isinstance(args.get("tickets"), list) else {"tickets": args["tickets"]}
