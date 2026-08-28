"""Costed evidence API for canonical Case 16."""

from __future__ import annotations

from typing import Any

from benchmark.cores.case_16_series_bundle import runtime_data
from benchmark.cores.case_16_series_bundle import world
from benchmark.cores.case_16_series_bundle.observations import (
    _observe,
    _series_observation,
    _title_observation,
)
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
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


class SeriesBundleAPI:
    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state
        self._trajectory: list[dict[str, Any]] = []
        self._evaluated = False
        self._submitted = False

    def tool_schemas(self) -> list[dict[str, Any]]:
        string = {"type": "string"}
        lots = {"type": "array", "items": string}
        return [
            _schema("read_title", "Read both lots and base values for one title.", {"title": string}, ["title"]),
            _schema(
                "read_series",
                "Read one complete signed compatibility table over public title positions.",
                {"series": string},
                ["series"],
            ),
            _schema(
                "read_series_page",
                "Read one canonical disjoint series page as an encoding, ordered columns, and compact rows: start is 0,24,48,... and length is 24 except for the final series_count-start remainder.",
                {
                    "start": {"type": "integer", "minimum": 0},
                    "length": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": runtime_data._SERIES_PAGE_SIZE,
                    },
                },
                ["start", "length"],
            ),
            _schema("read_title_index", "Read lot and incident-series handles for one title.", {"title": string}, ["title"]),
            _schema(
                "read_catalog_window",
                "Read title lot economics at two or three consecutive positions; series evidence is separate.",
                {"start": {"type": "integer", "minimum": 0}, "length": {"type": "integer", "enum": [2, 3]}},
                ["start", "length"],
            ),
            _schema("evaluate_portfolio", "Run the fully costed settlement audit for one caller-supplied complete portfolio; its cost exceeds a complete discovery plan.", {"lots": lots}, ["lots"]),
            _schema(SUBMIT_TOOL, "Submit a binding one-shot lot portfolio.", {"lots": lots}, ["lots"]),
        ]

    @property
    def _documents(self) -> dict[str, Any]:
        return self._state["source_documents"]

    def _record(self, tool: str, args: dict, result: dict) -> dict:
        self._trajectory.append({"fn": tool, "args": args, "result": result})
        return result

    def read_title(self, title: str) -> dict:
        if title not in self._documents["title_order"]:
            raise ValueError("unknown title")
        return self._record("read_title", {"title": title}, _title_observation(self._documents, title))

    def read_series(self, series: str) -> dict:
        if series not in self._documents["series_order"]:
            raise ValueError("unknown series")
        return self._record("read_series", {"series": series}, _series_observation(self._documents, series))

    def read_series_page(self, start: int, length: int) -> dict:
        size = len(self._documents["series_order"])
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(length, bool)
            or not isinstance(length, int)
            or start < 0
            or length < 1
            or length > runtime_data._SERIES_PAGE_SIZE
            or start + length > size
            or (start, length) not in set(runtime_data.series_page_partition(size))
        ):
            raise ValueError("invalid or noncanonical series page")
        args = {"start": start, "length": length}
        result = _observe(
            self._state, QueryCall("runtime-series-page", "read_series_page", args)
        )
        return self._record("read_series_page", args, result)

    def read_title_index(self, title: str) -> dict:
        if title not in self._documents["title_order"]:
            raise ValueError("unknown title")
        result = _observe(self._state, QueryCall("runtime-index", "read_title_index", {"title": title}))
        return self._record("read_title_index", {"title": title}, result)

    def read_catalog_window(self, start: int, length: int) -> dict:
        size = len(self._documents["title_order"])
        if isinstance(start, bool) or not isinstance(start, int) or length not in (2, 3) or start < 0 or start + length > size:
            raise ValueError("invalid catalog window")
        args = {"start": start, "length": length}
        result = _observe(self._state, QueryCall("runtime-window", "read_catalog_window", args))
        return self._record("read_catalog_window", args, result)

    def evaluate_portfolio(self, lots: list[str]) -> dict:
        args = {"lots": lots}
        if self._evaluated:
            return self._record(
                "evaluate_portfolio", args, {"error": "already evaluated"}
            )
        # A malformed or illegal candidate consumes the same one verification
        # opportunity as a legal candidate.
        self._evaluated = True
        result = _observe(self._state, QueryCall("runtime-evaluate", "evaluate_portfolio", args))
        return self._record("evaluate_portfolio", args, result)

    def submit_portfolio(self, lots: list[str]) -> dict:
        if self._submitted:
            return self._record(SUBMIT_TOOL, {"lots": lots}, {"error": "already submitted"})
        self._submitted = True
        legal, value = world.validate(self._state, {"lots": lots})
        return self._record(
            SUBMIT_TOOL,
            {"lots": lots},
            {"accepted": True, "legal": legal, "settled_value": value},
        )

    def trajectory(self) -> list[dict[str, Any]]:
        return list(self._trajectory)


def dispatch(instance_api: SeriesBundleAPI, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool not in (*QUERY_TOOLS, SUBMIT_TOOL):
        raise ValueError(f"unknown tool: {tool!r}")
    return getattr(instance_api, tool)(**args)


def extract_submission(trajectory: list[dict[str, Any]]) -> dict[str, Any] | None:
    args = first_submission_args(trajectory, SUBMIT_TOOL)
    return None if args is None or not isinstance(args.get("lots"), list) else {"lots": args["lots"]}
