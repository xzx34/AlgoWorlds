"""Load and validate the curated AlgoWorlds benchmark manifest."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from algoworlds.identity import (
    BENCHMARK_ID,
    TASK_FAMILIES,
    ToolInterface,
    iter_algorithmic_worlds,
)


DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "benchmark" / "MANIFEST.json"
SCHEMA_VERSION = "algoworlds_benchmark_manifest/2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_SNAPSHOT_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_EXPECTED_DIMENSIONS = {
    "task_families": 10,
    "workload_levels": ["L1", "L2", "L3", "L4"],
    "instances_per_family_level": 3,
    "hidden_instances": 120,
    "tool_interfaces": ["direct", "mediated"],
    "algorithmic_worlds": 240,
}


class ManifestError(ValueError):
    """The curated manifest or one of its bindings is inconsistent."""


def manifest_sha256(path: str | Path = DEFAULT_MANIFEST_PATH) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repository_root(path: str | Path = DEFAULT_MANIFEST_PATH) -> Path:
    """Return the release root for ``benchmark/MANIFEST.json``."""

    source = Path(path).resolve()
    if source.parent.name != "benchmark":
        raise ManifestError("the manifest must be located in a benchmark directory")
    return source.parent.parent


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ManifestError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _family_records(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = payload.get("task_families")
    if not isinstance(raw, list) or len(raw) != len(TASK_FAMILIES):
        raise ManifestError("manifest must declare exactly ten task families")
    result: dict[str, Mapping[str, Any]] = {}
    for index, record in enumerate(raw):
        if not isinstance(record, Mapping):
            raise ManifestError(f"task_families[{index}] must be an object")
        family_id = record.get("task_family_id")
        if not isinstance(family_id, str) or family_id in result:
            raise ManifestError("task-family identifiers must be unique strings")
        result[family_id] = record
    expected = [family.task_family_id for family in TASK_FAMILIES]
    if list(result) != expected:
        raise ManifestError("task families must match the canonical public roster")
    return result


def validate_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the release contract without reading bound artifacts."""

    if not isinstance(payload, Mapping):
        raise ManifestError("manifest root must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(f"unsupported manifest schema: {payload.get('schema_version')!r}")
    if payload.get("benchmark_id") != BENCHMARK_ID:
        raise ManifestError("unexpected benchmark_id")
    if payload.get("status") != "frozen":
        raise ManifestError("the bundled benchmark must be frozen")
    if payload.get("affiliation") != "Weixin AI":
        raise ManifestError("the public affiliation must be Weixin AI")
    if payload.get("dimensions") != _EXPECTED_DIMENSIONS:
        raise ManifestError("manifest dimensions do not describe the 240-world release")

    release = payload.get("release")
    if not isinstance(release, Mapping) or set(release) != {
        "release_id",
        "source_snapshot_digest",
    }:
        raise ManifestError("manifest release provenance is malformed")
    release_id = release.get("release_id")
    if not isinstance(release_id, str) or not release_id.strip():
        raise ManifestError("release.release_id must be a nonempty string")
    source_digest = release.get("source_snapshot_digest")
    if (
        not isinstance(source_digest, str)
        or _SOURCE_SNAPSHOT_DIGEST.fullmatch(source_digest) is None
    ):
        raise ManifestError(
            "release.source_snapshot_digest must be a sha256-prefixed digest"
        )

    release_scope = payload.get("release_scope")
    if not isinstance(release_scope, Mapping):
        raise ManifestError("manifest is missing release_scope")
    if release_scope.get("official_metric") != "exact_optimality":
        raise ManifestError("Exact optimality must be the only official metric")

    from algoworlds.runtime import RUNTIME_BY_FAMILY

    families = _family_records(payload)
    for family in TASK_FAMILIES:
        record = families[family.task_family_id]
        runtime = RUNTIME_BY_FAMILY[family.task_family_id]
        expected = {
            "display_name": family.display_name,
            "runtime_key": runtime.implementation_id,
            "objective_sense": runtime.objective_sense,
            "query_tools": list(runtime.query_tools),
            "submit_tool": runtime.submit_tool,
        }
        for field, value in expected.items():
            if record.get(field) != value:
                raise ManifestError(f"{family.task_family_id}.{field} is inconsistent")
        for field in ("instance_path_pattern", "certificate_path_pattern"):
            pattern = record.get(field)
            if not isinstance(pattern, str) or not pattern.startswith("benchmark/cores/"):
                raise ManifestError(f"{family.task_family_id}.{field} is malformed")
            try:
                pattern.format(
                    interface_index=0,
                    workload_index=1,
                    instance_zero_index=0,
                )
            except (IndexError, KeyError, ValueError) as exc:
                raise ManifestError(f"{family.task_family_id}.{field} is malformed") from exc
        prompts = record.get("prompts")
        if not isinstance(prompts, Mapping) or set(prompts) != {
            "environment",
            "user_request",
        }:
            raise ManifestError(f"{family.task_family_id}.prompts is malformed")
        for prompt_name, binding in prompts.items():
            if (
                not isinstance(binding, Mapping)
                or set(binding) != {"path"}
                or not isinstance(binding.get("path"), str)
            ):
                raise ManifestError(
                    f"{family.task_family_id}.prompts.{prompt_name} is malformed"
                )

    integrity = payload.get("artifact_integrity")
    if not isinstance(integrity, Mapping):
        raise ManifestError("manifest is missing artifact_integrity")
    if integrity.get("digest_algorithm") != "sha256_bytes/1":
        raise ManifestError("unsupported artifact digest algorithm")
    expected_counts = {"instances": 240, "certificates": 240, "prompts": 20}
    for group, expected_count in expected_counts.items():
        binding = integrity.get(group)
        if (
            not isinstance(binding, Mapping)
            or set(binding) != {"count", "files"}
            or binding.get("count") != expected_count
        ):
            raise ManifestError(f"artifact_integrity.{group}.count must be {expected_count}")
        files = binding.get("files")
        if not isinstance(files, Mapping) or len(files) != expected_count:
            raise ManifestError(
                f"artifact_integrity.{group}.files must contain {expected_count} entries"
            )
        expected_paths = set(artifact_paths(payload, group))
        if set(files) != expected_paths:
            raise ManifestError(
                f"artifact_integrity.{group}.files does not match the release roster"
            )
        for relative_path, digest in files.items():
            _require_sha256(
                digest,
                f"artifact_integrity.{group}.files[{relative_path!r}]",
            )

    return dict(payload)


def load_raw_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read manifest {source}: {exc}") from exc
    return validate_manifest(payload)


def _format_artifact(pattern: str, identity: Any) -> str:
    return pattern.format(
        interface_index=0 if identity.tool_interface is ToolInterface.DIRECT else 1,
        workload_index=int(identity.workload_level.value[1:]),
        instance_zero_index=identity.instance_index - 1,
    )


def expand_worlds(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expand the compact artifact layout into the canonical 240-world roster."""

    families = _family_records(payload)
    worlds: list[dict[str, Any]] = []
    for identity in iter_algorithmic_worlds():
        family = families[identity.task_family_id]
        record = identity.as_record()
        record.update(
            {
                "objective_sense": family["objective_sense"],
                "instance_artifact": _format_artifact(
                    family["instance_path_pattern"], identity
                ),
                "certificate_artifact": _format_artifact(
                    family["certificate_path_pattern"], identity
                ),
            }
        )
        worlds.append(record)
    if len(worlds) != 240 or len({item["algorithmic_world_id"] for item in worlds}) != 240:
        raise ManifestError("manifest does not expand to 240 unique algorithmic worlds")
    return worlds


def load_public_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    """Load the compact manifest and attach its expanded public world roster."""

    payload = load_raw_manifest(path)
    payload["manifest_sha256"] = manifest_sha256(path)
    payload["algorithmic_worlds"] = expand_worlds(payload)
    return payload


def artifact_paths(payload: Mapping[str, Any], group: str) -> tuple[str, ...]:
    if group == "instances":
        paths = [record["instance_artifact"] for record in expand_worlds(payload)]
    elif group == "certificates":
        paths = [record["certificate_artifact"] for record in expand_worlds(payload)]
    elif group == "prompts":
        paths = [
            binding["path"]
            for family in _family_records(payload).values()
            for binding in family["prompts"].values()
        ]
    else:
        raise ManifestError(f"unknown artifact group: {group!r}")
    if len(paths) != len(set(paths)):
        raise ManifestError(f"artifact group {group!r} contains duplicate paths")
    return tuple(sorted(paths))


def resolve_artifact(root: Path, relative_path: str) -> Path:
    if not isinstance(relative_path, str):
        raise ManifestError("artifact path must be a string")
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ManifestError(f"artifact path escapes the release root: {relative_path!r}") from exc
    return candidate


def artifact_sha256(
    payload: Mapping[str, Any], group: str, relative_path: str
) -> str:
    """Return the manifest-bound byte digest for one release artifact."""

    integrity = payload.get("artifact_integrity")
    binding = integrity.get(group) if isinstance(integrity, Mapping) else None
    files = binding.get("files") if isinstance(binding, Mapping) else None
    digest = files.get(relative_path) if isinstance(files, Mapping) else None
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise ManifestError(
            f"artifact is not bound by artifact_integrity.{group}: {relative_path!r}"
        )
    return digest


def artifact_tree_sha256(root: Path, paths: Iterable[str]) -> str:
    """Hash sorted ``path NUL bytes NUL`` records for one artifact group."""

    digest = hashlib.sha256()
    for relative_path in sorted(paths):
        source = resolve_artifact(root, relative_path)
        try:
            data = source.read_bytes()
        except OSError as exc:
            raise ManifestError(f"cannot read artifact {relative_path}: {exc}") from exc
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


__all__ = (
    "DEFAULT_MANIFEST_PATH",
    "ManifestError",
    "SCHEMA_VERSION",
    "artifact_sha256",
    "artifact_paths",
    "artifact_tree_sha256",
    "expand_worlds",
    "load_public_manifest",
    "load_raw_manifest",
    "manifest_sha256",
    "repository_root",
    "resolve_artifact",
    "validate_manifest",
)
