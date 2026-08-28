"""Public identities for AlgoWorlds hidden instances and algorithmic worlds."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum


BENCHMARK_ID = "algoworlds"


class IdentityError(ValueError):
    """An AlgoWorlds public identity is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class TaskFamily:
    """One public optimization task family."""

    task_family_id: str
    display_name: str

    def as_record(self) -> dict[str, str]:
        return {
            "task_family_id": self.task_family_id,
            "display_name": self.display_name,
        }


class ToolInterface(StrEnum):
    """The tool interface through which a hidden instance is exposed."""

    DIRECT = "direct"
    MEDIATED = "mediated"


class WorkloadLevel(StrEnum):
    """A certified workload level."""

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


TASK_FAMILIES = (
    TaskFamily("transit_routing", "Transit Routing"),
    TaskFamily("basket_assembly", "Basket Assembly"),
    TaskFamily("station_siting", "Station Siting"),
    TaskFamily("authorization_planning", "Authorization Planning"),
    TaskFamily("series_portfolio", "Series Portfolio"),
    TaskFamily("machine_layout", "Machine Layout"),
    TaskFamily("sequential_matching", "Sequential Matching"),
    TaskFamily("fleet_dispatch", "Fleet Dispatch"),
    TaskFamily("evidence_joined_routing", "Evidence-Joined Routing"),
    TaskFamily("migration_portfolio", "Migration Portfolio"),
)
TASK_FAMILY_BY_ID = {family.task_family_id: family for family in TASK_FAMILIES}

if len(TASK_FAMILY_BY_ID) != len(TASK_FAMILIES):
    raise RuntimeError("task-family identifiers must be unique")

_INSTANCE_INDICES = frozenset({1, 2, 3})
_ALGORITHMIC_WORLD_RE = re.compile(
    rf"^{BENCHMARK_ID}/"
    r"(?P<task_family_id>[a-z][a-z0-9_]*)/"
    r"(?P<workload_level>L[1-4])/"
    r"instance-(?P<instance_index>[1-3])/"
    r"(?P<tool_interface>direct|mediated)$"
)


def _task_family(value: str | TaskFamily) -> TaskFamily:
    task_family_id = value.task_family_id if isinstance(value, TaskFamily) else value
    if not isinstance(task_family_id, str):
        raise IdentityError("task_family_id must be a string")
    try:
        return TASK_FAMILY_BY_ID[task_family_id]
    except KeyError as exc:
        raise IdentityError(f"unknown task family: {task_family_id!r}") from exc


def _workload_level(value: str | WorkloadLevel) -> WorkloadLevel:
    try:
        return WorkloadLevel(value)
    except (TypeError, ValueError) as exc:
        raise IdentityError("workload_level must be one of L1, L2, L3, or L4") from exc


def _tool_interface(value: str | ToolInterface) -> ToolInterface:
    try:
        return ToolInterface(value)
    except (TypeError, ValueError) as exc:
        raise IdentityError("tool_interface must be either 'direct' or 'mediated'") from exc


def _instance_index(value: int) -> int:
    if isinstance(value, bool) or value not in _INSTANCE_INDICES:
        raise IdentityError("instance_index must be 1, 2, or 3")
    return value


def hidden_instance_id(
    *,
    task_family_id: str | TaskFamily,
    workload_level: str | WorkloadLevel,
    instance_index: int,
) -> str:
    """Build the canonical ID for one hidden optimization instance."""

    family = _task_family(task_family_id)
    level = _workload_level(workload_level)
    index = _instance_index(instance_index)
    return f"{BENCHMARK_ID}/{family.task_family_id}/{level.value}/instance-{index}"


def algorithmic_world_id(
    *,
    task_family_id: str | TaskFamily,
    workload_level: str | WorkloadLevel,
    instance_index: int,
    tool_interface: str | ToolInterface,
) -> str:
    """Build the canonical ID for one algorithmic world."""

    instance_id = hidden_instance_id(
        task_family_id=task_family_id,
        workload_level=workload_level,
        instance_index=instance_index,
    )
    interface = _tool_interface(tool_interface)
    return f"{instance_id}/{interface.value}"


@dataclass(frozen=True, slots=True)
class AlgorithmicWorldIdentity:
    """The complete public coordinates of one AlgoWorlds algorithmic world."""

    task_family: TaskFamily
    workload_level: WorkloadLevel
    instance_index: int
    tool_interface: ToolInterface

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_family", _task_family(self.task_family))
        object.__setattr__(
            self,
            "workload_level",
            _workload_level(self.workload_level),
        )
        object.__setattr__(self, "instance_index", _instance_index(self.instance_index))
        object.__setattr__(
            self,
            "tool_interface",
            _tool_interface(self.tool_interface),
        )

    @property
    def benchmark_id(self) -> str:
        return BENCHMARK_ID

    @property
    def task_family_id(self) -> str:
        return self.task_family.task_family_id

    @property
    def task_family_name(self) -> str:
        return self.task_family.display_name

    @property
    def hidden_instance_id(self) -> str:
        return hidden_instance_id(
            task_family_id=self.task_family,
            workload_level=self.workload_level,
            instance_index=self.instance_index,
        )

    @property
    def algorithmic_world_id(self) -> str:
        return algorithmic_world_id(
            task_family_id=self.task_family,
            workload_level=self.workload_level,
            instance_index=self.instance_index,
            tool_interface=self.tool_interface,
        )

    def as_record(self) -> dict[str, str | int]:
        """Return a JSON-compatible record containing only public fields."""

        return {
            "benchmark_id": self.benchmark_id,
            "algorithmic_world_id": self.algorithmic_world_id,
            "hidden_instance_id": self.hidden_instance_id,
            "task_family_id": self.task_family_id,
            "task_family_name": self.task_family_name,
            "workload_level": self.workload_level.value,
            "instance_index": self.instance_index,
            "tool_interface": self.tool_interface.value,
        }


def _identity(
    *,
    task_family_id: str | TaskFamily,
    workload_level: str | WorkloadLevel,
    instance_index: int,
    tool_interface: str | ToolInterface,
) -> AlgorithmicWorldIdentity:
    return AlgorithmicWorldIdentity(
        task_family=_task_family(task_family_id),
        workload_level=_workload_level(workload_level),
        instance_index=_instance_index(instance_index),
        tool_interface=_tool_interface(tool_interface),
    )


def identity_from_algorithmic_world_id(value: str) -> AlgorithmicWorldIdentity:
    """Parse a canonical algorithmic-world ID."""

    if not isinstance(value, str):
        raise IdentityError("algorithmic_world_id must be a string")
    match = _ALGORITHMIC_WORLD_RE.fullmatch(value)
    if match is None:
        raise IdentityError(f"malformed algorithmic-world ID: {value!r}")
    return _identity(
        task_family_id=match.group("task_family_id"),
        workload_level=match.group("workload_level"),
        instance_index=int(match.group("instance_index")),
        tool_interface=match.group("tool_interface"),
    )


def iter_algorithmic_worlds() -> Iterator[AlgorithmicWorldIdentity]:
    """Yield all 240 algorithmic worlds in canonical public order."""

    for family in TASK_FAMILIES:
        for level in WorkloadLevel:
            for instance_index in sorted(_INSTANCE_INDICES):
                for interface in ToolInterface:
                    yield _identity(
                        task_family_id=family,
                        workload_level=level,
                        instance_index=instance_index,
                        tool_interface=interface,
                    )


__all__ = (
    "BENCHMARK_ID",
    "TASK_FAMILIES",
    "TASK_FAMILY_BY_ID",
    "AlgorithmicWorldIdentity",
    "IdentityError",
    "TaskFamily",
    "ToolInterface",
    "WorkloadLevel",
    "algorithmic_world_id",
    "hidden_instance_id",
    "identity_from_algorithmic_world_id",
    "iter_algorithmic_worlds",
)
