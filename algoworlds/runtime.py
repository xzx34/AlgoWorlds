"""Curated runtime for the 240 released AlgoWorlds environments."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from algoworlds.identity import TASK_FAMILY_BY_ID
from algoworlds.runtime_core import CostModel, budget_rejection_result
from benchmark.cores.case_01_subway_transfers import api as transit_api
from benchmark.cores.case_01_subway_transfers import world as transit_world
from benchmark.cores.case_03_basket_assembly import api as basket_api
from benchmark.cores.case_03_basket_assembly import world as basket_world
from benchmark.cores.case_07_station_siting import api as siting_api
from benchmark.cores.case_07_station_siting import world as siting_world
from benchmark.cores.case_14_override import api as authorization_api
from benchmark.cores.case_14_override import world as authorization_world
from benchmark.cores.case_16_series_bundle import api as series_api
from benchmark.cores.case_16_series_bundle import world as series_world
from benchmark.cores.case_17_machine_layout import api as layout_api
from benchmark.cores.case_17_machine_layout import world as layout_world
from benchmark.cores.case_18_match_pairing import api as matching_api
from benchmark.cores.case_18_match_pairing import world as matching_world
from benchmark.cores.case_19_fleet_dispatch import api as fleet_api
from benchmark.cores.case_19_fleet_dispatch import world as fleet_world
from benchmark.cores.case_20_evidence_join import api as evidence_api
from benchmark.cores.case_20_evidence_join import world as evidence_world
from benchmark.cores.case_21_fixed_charge_migration import api as migration_api
from benchmark.cores.case_21_fixed_charge_migration import world as migration_world


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_PLACEHOLDER = re.compile(r"<[a-z][a-z0-9_]*>")


@dataclass(frozen=True, slots=True)
class FamilyRuntime:
    """The model-facing tools and final-decision checker for one task family."""

    task_family_id: str
    implementation_id: str
    objective_sense: str
    api_factory: Callable[[dict[str, Any]], Any]
    dispatch: Callable[[Any, str, dict[str, Any]], dict[str, Any]]
    extract_submission: Callable[[list[dict[str, Any]]], dict[str, Any] | None]
    validate: Callable[[dict[str, Any], Any], tuple[bool, int | None]]
    query_tools: tuple[str, ...]
    submit_tool: str
    prompt_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.task_family_id not in TASK_FAMILY_BY_ID:
            raise ValueError(f"unknown task family: {self.task_family_id!r}")
        if self.objective_sense not in {"min", "max"}:
            raise ValueError("objective_sense must be 'min' or 'max'")
        if self.submit_tool in self.query_tools:
            raise ValueError("the terminal tool cannot also be a query tool")

    @property
    def prompt_directory(self) -> Path:
        return (
            REPOSITORY_ROOT
            / "benchmark"
            / "cores"
            / self.implementation_id
            / "prompts"
        )

    def make_api(self, state: dict[str, Any]) -> Any:
        return self.api_factory(state)

    def tool_schemas(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        schemas = self.make_api(state).tool_schemas()
        names = {
            schema.get("function", {}).get("name")
            for schema in schemas
            if isinstance(schema, Mapping)
        }
        expected = set((*self.query_tools, self.submit_tool))
        if names != expected:
            raise ValueError(
                f"tool schema mismatch for {self.task_family_id}: "
                f"expected {sorted(expected)}, got {sorted(str(x) for x in names)}"
            )
        return schemas

    def cost_model(self, state: Mapping[str, Any]) -> CostModel:
        raw = state.get("cost_vector")
        if not isinstance(raw, Mapping):
            raw = state.get("query_costs")
        if not isinstance(raw, Mapping):
            raise ValueError("instance is missing its query cost vector")
        costs = {str(tool): cost for tool, cost in raw.items()}
        if set(costs) != set(self.query_tools):
            raise ValueError(
                f"query cost vector mismatch for {self.task_family_id}"
            )
        return CostModel(costs)

    def cost_budget(self, state: Mapping[str, Any]) -> int:
        value = state.get("cost_budget")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("instance cost_budget must be a nonnegative integer")
        return value

    def render_prompt(self, state: Mapping[str, Any]) -> tuple[str, str]:
        """Render the frozen environment and request without exposing private data."""

        environment = (self.prompt_directory / "environment.md").read_text(
            encoding="utf-8"
        )
        request = (self.prompt_directory / "user_request.txt").read_text(
            encoding="utf-8"
        )
        public = state.get("public")
        public_values = public if isinstance(public, Mapping) else {}
        allowed = set(self.prompt_fields)
        values: dict[str, Any] = {
            field: public_values.get(field, state.get(field)) for field in allowed
        }
        values["cost_budget"] = self.cost_budget(state)
        values["tool_costs"] = ", ".join(
            f"{name}={cost}"
            for name, cost in sorted(self.cost_model(state).costs.items())
        )

        def render(template: str) -> str:
            for field, value in values.items():
                marker = f"<{field}>"
                if isinstance(value, (list, tuple)):
                    replacement = ", ".join(str(item) for item in value)
                elif value is None:
                    continue
                else:
                    replacement = str(value)
                template = template.replace(marker, replacement)
            unresolved = sorted(set(_PLACEHOLDER.findall(template)))
            if unresolved:
                raise ValueError(
                    f"unresolved prompt fields for {self.task_family_id}: "
                    + ", ".join(unresolved)
                )
            return template.rstrip() + "\n"

        return render(environment), render(request)


_RUNTIMES = (
    FamilyRuntime(
        "transit_routing",
        "case_01_subway_transfers",
        "min",
        transit_api.SubwayAPI,
        transit_api.dispatch,
        transit_api.extract_submission,
        transit_world.validate,
        transit_api.QUERY_TOOLS,
        transit_api.SUBMIT_TOOL,
    ),
    FamilyRuntime(
        "basket_assembly",
        "case_03_basket_assembly",
        "min",
        basket_api.BasketAPI,
        basket_api.dispatch,
        basket_api.extract_submission,
        basket_world.validate,
        basket_api.QUERY_TOOLS,
        basket_api.SUBMIT_TOOL,
        ("item_count", "catalog_size"),
    ),
    FamilyRuntime(
        "station_siting",
        "case_07_station_siting",
        "max",
        siting_api.StationSitingAPI,
        siting_api.dispatch,
        siting_api.extract_submission,
        siting_world.validate,
        siting_api.QUERY_TOOLS,
        siting_api.SUBMIT_TOOL,
        (
            "facility_limit",
            "max_extended_sites",
            "interaction_bandwidth",
            "demand_count",
            "zone_handles",
            "demand_handles",
        ),
    ),
    FamilyRuntime(
        "authorization_planning",
        "case_14_override",
        "min",
        authorization_api.OverrideAPI,
        authorization_api.dispatch,
        authorization_api.extract_submission,
        authorization_world.validate,
        authorization_api.QUERY_TOOLS,
        authorization_api.SUBMIT_TOOL,
        ("stage_count", "plays_per_stage", "stage_handles_text"),
    ),
    FamilyRuntime(
        "series_portfolio",
        "case_16_series_bundle",
        "max",
        series_api.SeriesBundleAPI,
        series_api.dispatch,
        series_api.extract_submission,
        series_world.validate,
        series_api.QUERY_TOOLS,
        series_api.SUBMIT_TOOL,
        (
            "group_count",
            "series_count",
            "max_series_span",
            "title_handles_text",
            "series_handles_text",
        ),
    ),
    FamilyRuntime(
        "machine_layout",
        "case_17_machine_layout",
        "min",
        layout_api.MachineLayoutAPI,
        layout_api.dispatch,
        layout_api.extract_submission,
        layout_world.validate,
        layout_api.QUERY_TOOLS,
        layout_api.SUBMIT_TOOL,
    ),
    FamilyRuntime(
        "sequential_matching",
        "case_18_match_pairing",
        "min",
        matching_api.PairingAPI,
        matching_api.dispatch,
        matching_api.extract_submission,
        matching_world.validate,
        matching_api.QUERY_TOOLS,
        matching_api.SUBMIT_TOOL,
        (
            "participants_per_side",
            "participant_count",
            "pair_catalog_size",
            "handoff_catalog_size",
            "participant_handles_text",
        ),
    ),
    FamilyRuntime(
        "fleet_dispatch",
        "case_19_fleet_dispatch",
        "min",
        fleet_api.FleetDispatchAPI,
        fleet_api.dispatch,
        fleet_api.extract_submission,
        fleet_world.validate,
        fleet_api.QUERY_TOOLS,
        fleet_api.SUBMIT_TOOL,
        ("vehicle_handles", "job_handles"),
    ),
    FamilyRuntime(
        "evidence_joined_routing",
        "case_20_evidence_join",
        "min",
        evidence_api.EvidenceJoinAPI,
        evidence_api.dispatch,
        evidence_api.extract_submission,
        evidence_world.validate,
        evidence_api.QUERY_TOOLS,
        evidence_api.SUBMIT_TOOL,
        (
            "source",
            "destination",
            "decision_layers",
            "layer_width",
            "stage_handles",
            "component_handle",
            "residue_modulus",
            "required_residue",
        ),
    ),
    FamilyRuntime(
        "migration_portfolio",
        "case_21_fixed_charge_migration",
        "min",
        migration_api.MigrationAPI,
        migration_api.dispatch,
        migration_api.extract_submission,
        migration_world.validate,
        migration_api.QUERY_TOOLS,
        migration_api.SUBMIT_TOOL,
        ("group_count", "group_handles_text"),
    ),
)
RUNTIME_BY_FAMILY = {runtime.task_family_id: runtime for runtime in _RUNTIMES}

if set(RUNTIME_BY_FAMILY) != set(TASK_FAMILY_BY_ID):
    raise RuntimeError("runtime registry must cover all task families exactly once")


def runtime_for(task_family_id: str) -> FamilyRuntime:
    try:
        return RUNTIME_BY_FAMILY[task_family_id]
    except KeyError as exc:
        raise ValueError(f"unknown task family: {task_family_id!r}") from exc


def load_frozen_state(path: str | Path) -> dict[str, Any]:
    """Load the model-hidden payload from one immutable instance artifact."""

    source = Path(path)
    envelope = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(envelope, dict) or not isinstance(envelope.get("payload"), dict):
        raise ValueError(f"malformed instance artifact: {source}")
    return envelope["payload"]


class WorldSession:
    """One cost-budgeted interaction with a frozen algorithmic world."""

    def __init__(self, runtime: FamilyRuntime, state: dict[str, Any]) -> None:
        self.runtime = runtime
        self.state = state
        self.api = runtime.make_api(state)
        self.cost_model = runtime.cost_model(state)
        self.max_cost = runtime.cost_budget(state)
        self.spent_cost = 0
        self.trajectory: list[dict[str, Any]] = []

    @property
    def tool_schemas(self) -> list[dict[str, Any]]:
        return self.api.tool_schemas()

    @property
    def final_decision(self) -> dict[str, Any] | None:
        return self.runtime.extract_submission(self.trajectory)

    def call(self, tool: str, args: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(tool, str) or not isinstance(args, Mapping):
            return {"error": "tool name and arguments are required"}
        arguments = dict(args)
        if tool in self.runtime.query_tools:
            cost = self.cost_model.cost_of(tool)
            if self.spent_cost + cost > self.max_cost:
                return budget_rejection_result(
                    self.max_cost,
                    self.spent_cost,
                    tool,
                    self.runtime.query_tools,
                    self.cost_model,
                )
        elif tool != self.runtime.submit_tool:
            return {"error": f"unknown tool: {tool!r}"}

        try:
            result = self.runtime.dispatch(self.api, tool, arguments)
        except (KeyError, TypeError, ValueError) as exc:
            result = {"error": str(exc)}
        if not isinstance(result, dict):
            result = {"error": "tool returned a non-object result"}
        if tool in self.runtime.query_tools:
            self.spent_cost += self.cost_model.cost_of(tool)
        self.trajectory.append({"fn": tool, "args": arguments, "result": result})
        return result


__all__ = (
    "FamilyRuntime",
    "REPOSITORY_ROOT",
    "RUNTIME_BY_FAMILY",
    "WorldSession",
    "load_frozen_state",
    "runtime_for",
)
