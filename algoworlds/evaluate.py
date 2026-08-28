"""Run one model against selected frozen AlgoWorlds environments."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from algoworlds.identity import IdentityError, identity_from_algorithmic_world_id
from algoworlds.manifest import (
    DEFAULT_MANIFEST_PATH,
    ManifestError,
    load_public_manifest,
    repository_root,
    resolve_artifact,
)
from algoworlds.providers import (
    ModelConfig,
    ModelConfigurationError,
    ProviderFailure,
    Transport,
    build_transport,
    load_model_config,
)
from algoworlds.release import ReleaseVerificationError, verify_release
from algoworlds.runtime import WorldSession, load_frozen_state, runtime_for
from algoworlds.scoring import SUBMISSIONS_SCHEMA_VERSION, score_trial


WORLD_RUN_SCHEMA_VERSION = "algoworlds_world_run/1"
PARTIAL_SUBMISSIONS_SCHEMA_VERSION = "algoworlds_partial_submissions/1"
RUN_SCHEMA_VERSION = "algoworlds_model_run/1"


class EvaluationError(ValueError):
    """The requested evaluation cannot be run or resumed safely."""


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"cannot read existing result {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationError(f"existing result is not a JSON object: {path}")
    return value


def _selected_worlds(
    manifest: Mapping[str, Any], requested: Sequence[str]
) -> list[Mapping[str, Any]]:
    records = manifest["algorithmic_worlds"]
    if not requested:
        return list(records)
    requested_set: set[str] = set()
    for world_id in requested:
        try:
            identity_from_algorithmic_world_id(world_id)
        except IdentityError as exc:
            raise EvaluationError(str(exc)) from exc
        if world_id in requested_set:
            raise EvaluationError(f"duplicate --algorithmic-world: {world_id}")
        requested_set.add(world_id)
    known = {record["algorithmic_world_id"] for record in records}
    unknown = sorted(requested_set - known)
    if unknown:
        raise EvaluationError(f"unknown algorithmic world: {unknown[0]}")
    return [record for record in records if record["algorithmic_world_id"] in requested_set]


def _world_result_path(results_dir: Path, index: int, world_id: str) -> Path:
    digest = hashlib.sha256(world_id.encode("utf-8")).hexdigest()[:12]
    return results_dir / "worlds" / f"{index:03d}-{digest}.json"


def _run_contract(
    config: ModelConfig,
    manifest: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    max_turns: int,
    timeout: float,
    concurrency: int,
) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "benchmark_manifest_sha256": manifest["manifest_sha256"],
        "official_metric": "exact_optimality",
        "complete_trial": len(records) == 240,
        "world_count": len(records),
        "algorithmic_world_ids": [record["algorithmic_world_id"] for record in records],
        "model": config.public_record(),
        "runtime": {
            "max_turns": max_turns,
            "timeout_seconds": timeout,
            "concurrency": concurrency,
        },
    }


def _prepare_results(
    results_dir: Path, contract: Mapping[str, Any], *, resume: bool
) -> None:
    run_path = results_dir / "run.json"
    if resume:
        if not run_path.is_file():
            raise EvaluationError("--resume requires an existing run.json")
        if _read_json(run_path) != contract:
            raise EvaluationError("existing run.json does not match this evaluation")
        return
    if run_path.exists() or (results_dir.exists() and any(results_dir.iterdir())):
        raise EvaluationError(
            "results directory is not empty; choose a new directory or pass --resume"
        )
    results_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_path, contract)


def _completed_resume_result(
    path: Path, world_id: str, manifest_sha256: str
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    result = _read_json(path)
    if result.get("schema_version") != WORLD_RUN_SCHEMA_VERSION:
        raise EvaluationError(f"existing world result has the wrong schema: {path}")
    if result.get("algorithmic_world_id") != world_id:
        raise EvaluationError(f"existing world result has the wrong ID: {path}")
    if result.get("benchmark_manifest_sha256") != manifest_sha256:
        raise EvaluationError(f"existing world result has the wrong manifest: {path}")
    return result if result.get("status") == "completed" else None


def _evaluate_world(
    record: Mapping[str, Any],
    *,
    manifest_sha256: str,
    root: Path,
    config: ModelConfig,
    transport: Transport,
    max_turns: int,
) -> dict[str, Any]:
    world_id = record["algorithmic_world_id"]
    runtime = runtime_for(record["task_family_id"])
    state = load_frozen_state(resolve_artifact(root, record["instance_artifact"]))
    session = WorldSession(runtime, state)
    environment, request = runtime.render_prompt(state)
    try:
        provider_run = transport.run(
            session, environment, request, max_turns=max_turns
        )
    except ProviderFailure as exc:
        return {
            "schema_version": WORLD_RUN_SCHEMA_VERSION,
            "benchmark_manifest_sha256": manifest_sha256,
            "algorithmic_world_id": world_id,
            "model_label": config.label,
            "status": "infrastructure_error",
            "error": str(exc),
            "final_decision": None,
            "tool_calls": session.trajectory,
        }
    return {
        "schema_version": WORLD_RUN_SCHEMA_VERSION,
        "benchmark_manifest_sha256": manifest_sha256,
        "algorithmic_world_id": world_id,
        "model_label": config.label,
        "status": "completed",
        "termination": provider_run.termination,
        "turns": provider_run.turns,
        "final_decision": session.final_decision,
        "tool_calls": session.trajectory,
    }


def run_evaluation(
    *,
    model_config_path: str | Path,
    results_dir: str | Path,
    algorithmic_world_ids: Sequence[str] = (),
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    concurrency: int = 1,
    max_turns: int = 128,
    timeout: float = 1200.0,
    resume: bool = False,
    dry_run: bool = False,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Validate or execute one model run; never aggregate an incomplete subset."""

    if isinstance(concurrency, bool) or concurrency < 1:
        raise EvaluationError("concurrency must be a positive integer")
    if isinstance(max_turns, bool) or max_turns < 1:
        raise EvaluationError("max_turns must be a positive integer")
    if timeout <= 0:
        raise EvaluationError("timeout must be positive")
    config = load_model_config(model_config_path)
    manifest = load_public_manifest(manifest_path)
    records = _selected_worlds(manifest, algorithmic_world_ids)
    verify_release(manifest_path)
    contract = _run_contract(
        config,
        manifest,
        records,
        max_turns=max_turns,
        timeout=timeout,
        concurrency=concurrency,
    )
    if dry_run:
        return {
            "status": "dry_run",
            "benchmark_manifest_sha256": manifest["manifest_sha256"],
            "world_count": len(records),
            "complete_trial": len(records) == 240,
            "model": config.public_record(),
        }

    active_transport = transport or build_transport(config, timeout)
    destination = Path(results_dir).resolve()
    _prepare_results(destination, contract, resume=resume)
    root = repository_root(manifest_path)
    outputs: dict[str, dict[str, Any]] = {}
    pending: list[tuple[int, Mapping[str, Any], Path]] = []
    for index, record in enumerate(records, start=1):
        world_id = record["algorithmic_world_id"]
        path = _world_result_path(destination, index, world_id)
        existing = (
            _completed_resume_result(path, world_id, manifest["manifest_sha256"])
            if resume
            else None
        )
        if existing is not None:
            outputs[world_id] = existing
        else:
            pending.append((index, record, path))

    def execute(item: tuple[int, Mapping[str, Any], Path]) -> tuple[str, dict[str, Any]]:
        _, record, path = item
        result = _evaluate_world(
            record,
            manifest_sha256=manifest["manifest_sha256"],
            root=root,
            config=config,
            transport=active_transport,
            max_turns=max_turns,
        )
        _write_json(path, result)
        return record["algorithmic_world_id"], result

    if concurrency == 1:
        for item in pending:
            world_id, result = execute(item)
            outputs[world_id] = result
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(execute, item) for item in pending]
            for future in concurrent.futures.as_completed(futures):
                world_id, result = future.result()
                outputs[world_id] = result

    failures = [
        world_id
        for world_id, result in outputs.items()
        if result.get("status") != "completed"
    ]
    if failures:
        return {
            "status": "blocked",
            "world_count": len(records),
            "infrastructure_error_count": len(failures),
            "results_dir": str(destination),
        }

    entries = [
        {
            "algorithmic_world_id": record["algorithmic_world_id"],
            "final_decision": outputs[record["algorithmic_world_id"]]["final_decision"],
        }
        for record in records
    ]
    complete = len(records) == 240
    submissions = {
        "schema_version": (
            SUBMISSIONS_SCHEMA_VERSION
            if complete
            else PARTIAL_SUBMISSIONS_SCHEMA_VERSION
        ),
        "benchmark_manifest_sha256": manifest["manifest_sha256"],
        "metadata": {"model_label": config.label},
        "entries": entries,
    }
    submissions_name = "submissions.json" if complete else "partial-submissions.json"
    _write_json(destination / submissions_name, submissions)
    if not complete:
        return {
            "status": "completed_subset",
            "world_count": len(records),
            "official_summary": None,
            "results_dir": str(destination),
        }

    # Re-verify the frozen release after model execution, immediately before
    # producing the official score.
    summary = score_trial(submissions, manifest_path=manifest_path)
    _write_json(destination / "score.json", summary)
    return {
        "status": "completed",
        "world_count": 240,
        "exact_optimal_count": summary["exact_optimal_count"],
        "exact_optimality_percent": summary["exact_optimality_percent"],
        "results_dir": str(destination),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="algoworlds evaluate",
        description="Evaluate one model on the curated AlgoWorlds release.",
    )
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument(
        "--algorithmic-world",
        action="append",
        default=[],
        metavar="ID",
        help="select one world; repeat as needed (default: all 240)",
    )
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--max-turns", type=int, default=128)
    parser.add_argument("--timeout", type=float, default=1200.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    try:
        result = run_evaluation(
            model_config_path=args.model_config,
            results_dir=args.results_dir,
            algorithmic_world_ids=args.algorithmic_world,
            manifest_path=args.manifest,
            concurrency=args.concurrency,
            max_turns=args.max_turns,
            timeout=args.timeout,
            resume=args.resume,
            dry_run=args.dry_run,
        )
    except (
        EvaluationError,
        ManifestError,
        ModelConfigurationError,
        ReleaseVerificationError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "EvaluationError",
    "PARTIAL_SUBMISSIONS_SCHEMA_VERSION",
    "RUN_SCHEMA_VERSION",
    "WORLD_RUN_SCHEMA_VERSION",
    "run_evaluation",
)
