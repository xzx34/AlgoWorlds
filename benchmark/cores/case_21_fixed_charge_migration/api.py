"""Costed discovery and binding submission API for Case 21."""

from __future__ import annotations

from typing import Any

from benchmark.cores.case_21_fixed_charge_migration import runtime_data
from benchmark.cores.case_21_fixed_charge_migration import world
from algoworlds.runtime_core import CostModel, first_submission_args


QUERY_TOOLS = tuple(runtime_data.QUERY_COSTS)
SUBMIT_TOOL = "submit_portfolio"
COST_MODEL = CostModel(dict(runtime_data.QUERY_COSTS))


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


class MigrationAPI:
    def __init__(self, world_state: dict[str, Any]) -> None:
        self._state = world_state
        self._trajectory: list[dict[str, Any]] = []
        self._evaluated = False
        self._submitted = False

    def tool_schemas(self) -> list[dict[str, Any]]:
        group = {"group": {"type": "string"}}
        window = {
            "start": {"type": "integer", "minimum": 0},
            "length": {"type": "integer", "enum": [2, 3]},
        }
        page = {"page": {"type": "integer", "minimum": 0}}
        packages = {"packages": {"type": "array", "items": {"type": "string"}}}
        return [
            _function(
                "read_catalog_group",
                "Read package identifiers and base costs for one public group.",
                group,
                ["group"],
            ),
            _function(
                "read_classification_group",
                "Read migration modes and zero-, one-, or two-domain support "
                "requirements for one public group.",
                group,
                ["group"],
            ),
            _function(
                "read_catalog_window",
                "Read catalog rows for two or three consecutive group positions.",
                window,
                ["start", "length"],
            ),
            _function(
                "read_classification_window",
                "Read classification rows for two or three consecutive group positions.",
                window,
                ["start", "length"],
            ),
            _function(
                "read_catalog_page",
                f"Read catalog page k: zero-based group-order positions "
                f"{runtime_data.PAGE_SIZE}k through "
                f"{runtime_data.PAGE_SIZE}k+{runtime_data.PAGE_SIZE - 1}.",
                page,
                ["page"],
            ),
            _function(
                "read_classification_page",
                f"Read classification page k: zero-based group-order positions "
                f"{runtime_data.PAGE_SIZE}k through "
                f"{runtime_data.PAGE_SIZE}k+{runtime_data.PAGE_SIZE - 1}.",
                page,
                ["page"],
            ),
            _function(
                "read_support_policy",
                "Read support-domain fixed charges and the assignment-independent "
                "objective offset.",
                {},
                [],
            ),
            _function(
                "evaluate_portfolio",
                "One-shot check returning only legality and scalar total cost for "
                "exactly the caller-supplied portfolio; no decomposition or "
                "recommendation. Any first call consumes the check.",
                packages,
                ["packages"],
            ),
            _function(
                SUBMIT_TOOL,
                "Submit one complete package portfolio. This is binding and one-shot.",
                packages,
                ["packages"],
            ),
        ]

    def _record(self, tool: str, args: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        self._trajectory.append({"fn": tool, "args": args, "result": result})
        return result

    @property
    def _documents(self) -> dict[str, Any]:
        return self._state["source_documents"]

    def _known_group(self, group: str) -> None:
        if group not in self._documents["group_order"]:
            raise ValueError("unknown group")

    def _window_groups(self, start: int, length: int) -> list[str]:
        if isinstance(start, bool) or not isinstance(start, int):
            raise ValueError("start must be an integer")
        if length not in (2, 3) or start < 0 or start + length > len(
            self._documents["group_order"]
        ):
            raise ValueError("window must be an in-range length-two/three interval")
        return self._documents["group_order"][start : start + length]

    def _page_groups(self, page: int) -> list[str]:
        pages = runtime_data.page_count(len(self._documents["group_order"]))
        if (
            isinstance(page, bool)
            or not isinstance(page, int)
            or not 0 <= page < pages
        ):
            raise ValueError("page must identify an existing fixed page")
        start = page * runtime_data.PAGE_SIZE
        return self._documents["group_order"][start : start + runtime_data.PAGE_SIZE]

    def _catalog_rows(self, groups: set[str]) -> list[dict[str, Any]]:
        return [row for row in self._documents["catalog"] if row["group_id"] in groups]

    def _classification_rows(self, groups: set[str]) -> dict[str, Any]:
        packages = {
            row["package_id"]
            for row in self._documents["catalog"]
            if row["group_id"] in groups
        }
        classification = self._documents["classification"]
        if classification["encoding"] == "direct":
            return {
                "encoding": "direct",
                "rows": [
                    row for row in classification["rows"] if row["package_id"] in packages
                ],
            }
        package_cohorts = [
            row
            for row in classification["package_cohorts"]
            if row["package_id"] in packages
        ]
        cohorts = {row["cohort_id"] for row in package_cohorts}
        return {
            "encoding": "mediated",
            "package_cohorts": package_cohorts,
            "cohort_terms": [
                row for row in classification["cohort_terms"] if row["cohort_id"] in cohorts
            ],
        }

    def read_catalog_group(self, group: str) -> dict[str, Any]:
        self._known_group(group)
        return self._record(
            "read_catalog_group", {"group": group}, {"rows": self._catalog_rows({group})}
        )

    def read_classification_group(self, group: str) -> dict[str, Any]:
        self._known_group(group)
        return self._record(
            "read_classification_group",
            {"group": group},
            self._classification_rows({group}),
        )

    def read_catalog_window(self, start: int, length: int) -> dict[str, Any]:
        groups = set(self._window_groups(start, length))
        return self._record(
            "read_catalog_window",
            {"start": start, "length": length},
            {"rows": self._catalog_rows(groups)},
        )

    def read_classification_window(self, start: int, length: int) -> dict[str, Any]:
        groups = set(self._window_groups(start, length))
        return self._record(
            "read_classification_window",
            {"start": start, "length": length},
            self._classification_rows(groups),
        )

    def read_catalog_page(self, page: int) -> dict[str, Any]:
        groups = set(self._page_groups(page))
        return self._record(
            "read_catalog_page",
            {"page": page},
            {"rows": self._catalog_rows(groups)},
        )

    def read_classification_page(self, page: int) -> dict[str, Any]:
        groups = set(self._page_groups(page))
        return self._record(
            "read_classification_page",
            {"page": page},
            self._classification_rows(groups),
        )

    def read_support_policy(self) -> dict[str, Any]:
        return self._record(
            "read_support_policy",
            {},
            {
                "rows": list(self._documents["support_policy"]),
                "objective_offset": self._documents["objective_offset"],
            },
        )

    def evaluate_portfolio(self, packages: list[str]) -> dict[str, Any]:
        if self._evaluated:
            return self._record(
                "evaluate_portfolio", {"packages": packages}, {"error": "already evaluated"}
            )
        self._evaluated = True
        try:
            total_cost = runtime_data.portfolio_breakdown(self._documents, packages)[
                "total_cost"
            ]
        except (KeyError, TypeError, ValueError):
            result = {"complete": False, "legal": False}
        else:
            result = {"complete": True, "legal": True, "total_cost": total_cost}
        return self._record("evaluate_portfolio", {"packages": packages}, result)

    def submit_portfolio(self, packages: list[str]) -> dict[str, Any]:
        if self._submitted:
            return self._record(
                SUBMIT_TOOL, {"packages": packages}, {"error": "already submitted"}
            )
        self._submitted = True
        legal, value = world.validate(self._state, {"packages": packages})
        return self._record(
            SUBMIT_TOOL,
            {"packages": packages},
            {"accepted": True, "legal": legal, "total_cost": value},
        )

    def trajectory(self) -> list[dict[str, Any]]:
        return list(self._trajectory)


def dispatch(api: MigrationAPI, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool not in (*QUERY_TOOLS, SUBMIT_TOOL):
        raise ValueError(f"unknown tool: {tool!r}")
    return getattr(api, tool)(**args)


def extract_submission(trajectory: list[dict[str, Any]]) -> dict[str, Any] | None:
    args = first_submission_args(trajectory, SUBMIT_TOOL)
    if args is None or not isinstance(args.get("packages"), list):
        return None
    return {"packages": args["packages"]}
