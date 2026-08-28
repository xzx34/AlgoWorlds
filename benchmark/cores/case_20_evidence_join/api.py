"""Positive-cost compact discovery API and binding submission for Case 20."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable


from .runtime_data import Instance
from .world import validate_path
from algoworlds.runtime_core import CostModel, first_submission_args


QUERY_COSTS = {
    "read_manifest_stage": 3,
    "read_exceptions_stage": 3,
    "read_manifest_window": 10,
    "read_exceptions_window": 10,
    "read_tariff_card": 2,
    "evaluate_path": 250,
}
SUBMIT_TOOL = "submit_path"
QUERY_TOOLS = tuple(QUERY_COSTS)
COST_MODEL = CostModel(dict(QUERY_COSTS))


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


class EvidenceJoinAPI:
    def __init__(
        self,
        instance: Instance,
        *,
        compact_catalog: dict[str, Any] | None = None,
    ) -> None:
        self._instance = instance
        self._spent = 0
        self._evaluated = False
        self._submitted = False
        self._trajectory: list[dict[str, Any]] = []
        self._compact_catalog = compact_catalog

    @property
    def budget(self) -> int:
        return int(self._instance["public"]["cost_budget"])

    @property
    def spent(self) -> int:
        return self._spent

    @property
    def remaining(self) -> int:
        return self.budget - self._spent

    @property
    def submitted(self) -> bool:
        return self._submitted

    def trajectory(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._trajectory]

    def tool_schemas(self) -> list[dict[str, Any]]:
        stage = {"type": "string", "description": "A listed stage handle."}
        length = {"type": "integer", "enum": [2, 3]}
        component = {"type": "string", "description": "The listed component handle."}
        edge_list = {"type": "array", "items": {"type": "string"}}
        return [
            _schema(
                "read_manifest_stage",
                "Read one of the d+1 ordered arc stages (node directory, physical edge ids, incidence, and packed quantity/residue). A legal path selects one connected row per stage.",
                {"stage": stage},
                ["stage"],
            ),
            _schema(
                "read_exceptions_stage",
                "Read tariff-class slots aligned with the compact manifest rows at one stage.",
                {"stage": stage},
                ["stage"],
            ),
            _schema(
                "read_manifest_window",
                "Read compact packed manifest views over two or three consecutive ordered arc stages.",
                {"start": stage, "length": length},
                ["start", "length"],
            ),
            _schema(
                "read_exceptions_window",
                "Read aligned tariff-class slots over two or three consecutive stages.",
                {"start": stage, "length": length},
                ["start", "length"],
            ),
            _schema(
                "read_tariff_card",
                "Read the rate vector indexed by the exception source's class slots.",
                {"component": component},
                ["component"],
            ),
            _schema(
                "evaluate_path",
                "Price and check the exact caller-supplied directed path without submitting it.",
                {"edges": edge_list},
                ["edges"],
            ),
            _schema(
                SUBMIT_TOOL,
                "Submit one final directed path. This call is binding and terminal.",
                {"edges": edge_list},
                ["edges"],
            ),
        ]

    def _record(
        self,
        tool: str,
        args: dict[str, Any],
        result: dict[str, Any],
        charged_cost: int,
    ) -> dict[str, Any]:
        self._trajectory.append({
            "fn": tool,
            "args": dict(args),
            "result": result,
            "charged_cost": charged_cost,
            "spent_after": self._spent,
        })
        return result

    def _query(
        self,
        tool: str,
        args: dict[str, Any],
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        if self._submitted:
            return self._record(tool, args, {"error": "round is terminal after submission"}, 0)
        cost = int(self._instance["cost_vector"][tool])
        if self._spent + cost > self.budget:
            return self._record(tool, args, {"error": "insufficient remaining budget"}, 0)
        self._spent += cost
        try:
            result = operation()
        except (TypeError, ValueError) as error:
            result = {"error": str(error)}
        return self._record(tool, args, result, cost)

    def _stage_index(self, stage: Any) -> int:
        handles = self._instance["public"]["stage_handles"]
        if not isinstance(stage, str) or stage not in handles:
            raise ValueError("unknown stage handle")
        return handles.index(stage)

    def _window_handles(self, start: Any, length: Any) -> list[str]:
        if not isinstance(length, int) or isinstance(length, bool) or length not in (2, 3):
            raise ValueError("window length must be two or three")
        index = self._stage_index(start)
        handles = self._instance["public"]["stage_handles"]
        if index + length > len(handles):
            raise ValueError("window exceeds the listed stages")
        return handles[index:index + length]

    def _catalog(self) -> dict[str, Any]:
        """Normalize either physical arm once into compact logical stage views."""

        if self._compact_catalog is not None:
            return self._compact_catalog

        # Imported lazily to avoid the runtime_data -> family -> api cycle.
        from .checker import canonical_source_documents, checksum_parameters

        documents, physical_projection, _ = canonical_source_documents(self._instance)
        modulus, _ = checksum_parameters(self._instance)
        exception_by_key = {
            row["semantic_key"]: row["tariff_class"] for row in documents["E"]
        }
        if len(exception_by_key) != len(documents["E"]):
            raise ValueError("duplicate canonical exception key")
        tariff_by_class = {
            row["tariff_class"]: row["rate"] for row in documents["T"]
        }
        if len(tariff_by_class) != len(documents["T"]):
            raise ValueError("duplicate canonical tariff class")
        class_handles = sorted(tariff_by_class)
        class_slots = {handle: slot for slot, handle in enumerate(class_handles)}

        manifest: dict[str, dict[str, Any]] = {}
        exceptions: dict[str, dict[str, Any]] = {}
        for stage in self._instance["public"]["stage_handles"]:
            stage_rows = sorted(
                (row for row in documents["M"] if row["stage"] == stage),
                key=lambda row: row["edge_id"],
            )
            nodes = sorted(
                {node for row in stage_rows for node in (row["tail"], row["head"])}
            )
            node_slots = {node: slot for slot, node in enumerate(nodes)}
            compact_rows: list[list[Any]] = []
            exception_slots: list[int] = []
            for row in stage_rows:
                projection = physical_projection.get(row["edge_id"])
                if not isinstance(projection, list) or len(projection) not in (1, 2):
                    raise ValueError("logical arc must project to one or two physical edges")
                compact_rows.append([
                    list(projection),
                    node_slots[row["tail"]],
                    node_slots[row["head"]],
                    row["tariff_quantity"] * modulus + row["residue_delta"],
                ])
                tariff_class = exception_by_key.get(row["semantic_key"])
                if tariff_class not in class_slots:
                    raise ValueError("canonical exception references an unknown tariff class")
                exception_slots.append(class_slots[tariff_class])
            manifest[stage] = {"stage": stage, "nodes": nodes, "rows": compact_rows}
            exceptions[stage] = {"stage": stage, "class_slots": exception_slots}

        self._compact_catalog = {
            "manifest": manifest,
            "exceptions": exceptions,
            "rates": [tariff_by_class[handle] for handle in class_handles],
            "residue_modulus": modulus,
        }
        return self._compact_catalog

    def _manifest_result(self, views: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "format": "compact_manifest_v2",
            "residue_modulus": self._catalog()["residue_modulus"],
            "stages": views,
        }

    @staticmethod
    def _exceptions_result(views: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "format": "compact_exceptions_v1",
            "stages": views,
        }

    def read_manifest_stage(self, stage: Any) -> dict[str, Any]:
        args = {"stage": stage}

        def operation() -> dict[str, Any]:
            self._stage_index(stage)
            return self._manifest_result([self._catalog()["manifest"][stage]])

        return self._query("read_manifest_stage", args, operation)

    def read_exceptions_stage(self, stage: Any) -> dict[str, Any]:
        args = {"stage": stage}

        def operation() -> dict[str, Any]:
            self._stage_index(stage)
            return self._exceptions_result([self._catalog()["exceptions"][stage]])

        return self._query("read_exceptions_stage", args, operation)

    def read_manifest_window(self, start: Any, length: Any) -> dict[str, Any]:
        args = {"start": start, "length": length}

        def operation() -> dict[str, Any]:
            handles = self._window_handles(start, length)
            return self._manifest_result([
                self._catalog()["manifest"][handle] for handle in handles
            ])

        return self._query("read_manifest_window", args, operation)

    def read_exceptions_window(self, start: Any, length: Any) -> dict[str, Any]:
        args = {"start": start, "length": length}

        def operation() -> dict[str, Any]:
            handles = self._window_handles(start, length)
            return self._exceptions_result([
                self._catalog()["exceptions"][handle] for handle in handles
            ])

        return self._query("read_exceptions_window", args, operation)

    def read_tariff_card(self, component: Any) -> dict[str, Any]:
        args = {"component": component}

        def operation() -> dict[str, Any]:
            if component != self._instance["public"]["component_handle"]:
                raise ValueError("unknown component handle")
            return {
                "format": "compact_tariff_v1",
                "rate_by_class_slot": list(self._catalog()["rates"]),
            }

        return self._query("read_tariff_card", args, operation)

    def evaluate_path(self, edges: Any) -> dict[str, Any]:
        args = {"edges": edges}

        if self._evaluated:
            return self._record(
                "evaluate_path", args, {"error": "already evaluated"}, 0
            )
        # Illegal candidates consume the sole scalar-feedback opportunity.
        # Together with the high verification price this prevents evaluator
        # replay from replacing the intended three-source join and DAG solve.
        self._evaluated = True

        def operation() -> dict[str, Any]:
            legal, total, error = validate_path(self._instance, edges)
            return {"legal": legal, "total_cost": total, "error": error}

        return self._query("evaluate_path", args, operation)

    def submit_path(self, edges: Any) -> dict[str, Any]:
        args = {"edges": edges}
        if self._submitted:
            return self._record(SUBMIT_TOOL, args, {"error": "already submitted"}, 0)
        self._submitted = True
        legal, total, error = validate_path(self._instance, edges)
        return self._record(
            SUBMIT_TOOL,
            args,
            {"submitted": True, "legal": legal, "total_cost": total, "reason": error},
            0,
        )


def dispatch(api: EvidenceJoinAPI, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool not in (*QUERY_COSTS, SUBMIT_TOOL):
        raise ValueError(f"unknown tool: {tool!r}")
    return getattr(api, tool)(**args)


def extract_submission(trajectory: list[dict[str, Any]]) -> dict[str, Any] | None:
    args = first_submission_args(trajectory, SUBMIT_TOOL)
    if args is None or not isinstance(args.get("edges"), list):
        return None
    return {"edges": args["edges"]}
