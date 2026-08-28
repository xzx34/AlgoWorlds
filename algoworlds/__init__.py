"""Public Python interface for the AlgoWorlds benchmark."""

from __future__ import annotations

from algoworlds.identity import (
    BENCHMARK_ID,
    TASK_FAMILIES,
    AlgorithmicWorldIdentity,
    IdentityError,
    TaskFamily,
    ToolInterface,
    WorkloadLevel,
    algorithmic_world_id,
    hidden_instance_id,
    identity_from_algorithmic_world_id,
    iter_algorithmic_worlds,
)
from algoworlds.manifest import load_public_manifest

__version__ = "0.1.0"


def score_decision(*args, **kwargs):
    """Lazily invoke the public single-world Exact-optimality scorer."""

    from algoworlds.scoring import score_decision as implementation

    return implementation(*args, **kwargs)


def score_trial(*args, **kwargs):
    """Lazily invoke the public complete-trial Exact-optimality scorer."""

    from algoworlds.scoring import score_trial as implementation

    return implementation(*args, **kwargs)

__all__ = (
    "BENCHMARK_ID",
    "TASK_FAMILIES",
    "AlgorithmicWorldIdentity",
    "IdentityError",
    "TaskFamily",
    "ToolInterface",
    "WorkloadLevel",
    "__version__",
    "algorithmic_world_id",
    "hidden_instance_id",
    "identity_from_algorithmic_world_id",
    "iter_algorithmic_worlds",
    "load_public_manifest",
    "score_decision",
    "score_trial",
)
