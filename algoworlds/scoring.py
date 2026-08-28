"""Exact-optimality scoring for the curated 240-world release."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from algoworlds.certificates import CertificateError, validate_exact_certificate
from algoworlds.identity import identity_from_algorithmic_world_id
from algoworlds.manifest import (
    DEFAULT_MANIFEST_PATH,
    ManifestError,
    artifact_sha256,
    load_public_manifest,
    repository_root,
    resolve_artifact,
)
from algoworlds.runtime import load_frozen_state, runtime_for


SUBMISSIONS_SCHEMA_VERSION = "algoworlds_submissions/1"
SUMMARY_SCHEMA_VERSION = "algoworlds_exact_optimality_summary/1"


class ScoringError(ValueError):
    """A submission set or certified scoring artifact is invalid."""


def _world_index(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    records = manifest.get("algorithmic_worlds")
    if not isinstance(records, list):
        raise ScoringError("manifest has no expanded world roster")
    return {record["algorithmic_world_id"]: record for record in records}


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoringError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ScoringError(f"{label} must contain a JSON object")
    return payload


def _certified_optimum(
    record: Mapping[str, Any], root: Path, manifest: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    instance_path = resolve_artifact(root, record["instance_artifact"])
    certificate_path = resolve_artifact(root, record["certificate_artifact"])
    try:
        expected_instance_sha256 = artifact_sha256(
            manifest, "instances", record["instance_artifact"]
        )
        expected_certificate_sha256 = artifact_sha256(
            manifest, "certificates", record["certificate_artifact"]
        )
        instance_bytes = instance_path.read_bytes()
        certificate_bytes = certificate_path.read_bytes()
    except (ManifestError, OSError) as exc:
        raise ScoringError(str(exc)) from exc
    if hashlib.sha256(instance_bytes).hexdigest() != expected_instance_sha256:
        raise ScoringError("instance bytes do not match the benchmark manifest")
    if hashlib.sha256(certificate_bytes).hexdigest() != expected_certificate_sha256:
        raise ScoringError("certificate bytes do not match the benchmark manifest")
    certificate = _read_json(certificate_path, "certificate")
    try:
        validated = validate_exact_certificate(
            certificate,
            algorithmic_world_id=record["algorithmic_world_id"],
            instance_sha256=expected_instance_sha256,
            objective_sense=record["objective_sense"],
        )
    except CertificateError as exc:
        raise ScoringError(str(exc)) from exc
    return load_frozen_state(instance_path), validated["certified_optimum"]


def _score_record(
    record: Mapping[str, Any],
    final_decision: Any,
    root: Path,
    manifest: Mapping[str, Any],
) -> int:
    state, optimum = _certified_optimum(record, root, manifest)
    if not isinstance(final_decision, Mapping):
        return 0
    runtime = runtime_for(record["task_family_id"])
    try:
        legal, objective = runtime.validate(state, dict(final_decision))
    except (AssertionError, IndexError, KeyError, TypeError, ValueError):
        return 0
    if not isinstance(legal, bool):
        raise ScoringError("final-decision checker returned a non-boolean legal flag")
    if objective is not None and (
        isinstance(objective, bool) or not isinstance(objective, int)
    ):
        raise ScoringError("final-decision checker returned a non-integer objective")
    return int(legal and objective is not None and objective == optimum)


def score_decision(
    algorithmic_world_id: str,
    final_decision: Any,
    *,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> int:
    """Return ``1`` only for a feasible, exactly optimal final decision."""

    try:
        identity_from_algorithmic_world_id(algorithmic_world_id)
        manifest = load_public_manifest(manifest_path)
    except (ManifestError, ValueError) as exc:
        raise ScoringError(str(exc)) from exc
    try:
        record = _world_index(manifest)[algorithmic_world_id]
    except KeyError as exc:
        raise ScoringError(f"unknown algorithmic world: {algorithmic_world_id!r}") from exc
    return _score_record(
        record,
        final_decision,
        repository_root(manifest_path),
        manifest,
    )


def _validated_entries(
    submissions: Mapping[str, Any], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    if submissions.get("schema_version") != SUBMISSIONS_SCHEMA_VERSION:
        raise ScoringError(
            f"schema_version must be {SUBMISSIONS_SCHEMA_VERSION!r}"
        )
    if submissions.get("benchmark_manifest_sha256") != manifest["manifest_sha256"]:
        raise ScoringError("submission manifest digest does not match this release")
    entries = submissions.get("entries")
    if not isinstance(entries, list):
        raise ScoringError("entries must be a JSON array")

    expected = set(_world_index(manifest))
    decisions: dict[str, Any] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ScoringError(f"entries[{index}] must be an object")
        world_id = entry.get("algorithmic_world_id")
        if not isinstance(world_id, str):
            raise ScoringError(f"entries[{index}].algorithmic_world_id must be a string")
        if world_id in decisions:
            raise ScoringError(f"duplicate algorithmic-world ID: {world_id}")
        if world_id not in expected:
            raise ScoringError(f"unknown algorithmic-world ID: {world_id}")
        if "final_decision" not in entry:
            raise ScoringError(f"entries[{index}] is missing final_decision")
        decisions[world_id] = entry["final_decision"]

    missing = sorted(expected - decisions.keys())
    if missing:
        raise ScoringError(
            f"official scoring requires all 240 worlds; missing {len(missing)}"
        )
    if len(decisions) != 240:
        raise ScoringError("official scoring requires exactly 240 entries")
    return decisions


def score_trial(
    submissions: Mapping[str, Any],
    *,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Score one complete 240-world trial under Exact optimality."""

    if not isinstance(submissions, Mapping):
        raise ScoringError("submissions must be a JSON object")
    try:
        manifest = load_public_manifest(manifest_path)
    except ManifestError as exc:
        raise ScoringError(str(exc)) from exc
    decisions = _validated_entries(submissions, manifest)
    from algoworlds.release import ReleaseVerificationError, verify_release

    try:
        verify_release(manifest_path)
    except (ManifestError, ReleaseVerificationError) as exc:
        raise ScoringError(str(exc)) from exc

    root = repository_root(manifest_path)
    records = manifest["algorithmic_worlds"]
    worlds = [
        {
            "algorithmic_world_id": record["algorithmic_world_id"],
            "exact_optimality": _score_record(
                record,
                decisions[record["algorithmic_world_id"]],
                root,
                manifest,
            ),
        }
        for record in records
    ]
    exact_count = sum(record["exact_optimality"] for record in worlds)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "benchmark_manifest_sha256": manifest["manifest_sha256"],
        "world_count": 240,
        "exact_optimal_count": exact_count,
        "exact_optimality_percent": round(100 * exact_count / 240, 6),
        "worlds": worlds,
    }


def load_submissions(path: str | Path) -> dict[str, Any]:
    return _read_json(Path(path), "submissions")


__all__ = (
    "SUBMISSIONS_SCHEMA_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "ScoringError",
    "load_submissions",
    "score_decision",
    "score_trial",
)
