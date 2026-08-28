"""Verify the curated release without replaying generation or solvers."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from algoworlds.certificates import CertificateError, validate_exact_certificate
from algoworlds.manifest import (
    DEFAULT_MANIFEST_PATH,
    ManifestError,
    artifact_paths,
    artifact_sha256,
    load_public_manifest,
    repository_root,
    resolve_artifact,
)
from algoworlds.runtime import WorldSession, load_frozen_state, runtime_for


VERIFICATION_SCHEMA_VERSION = "algoworlds_release_verification/1"
INSTANCE_SCHEMA_VERSION = "algoworlds_frozen_instance/1"
_INSTANCE_FIELDS = {
    "schema_version",
    "case_id",
    "arm_index",
    "rung_index",
    "world_index",
    "member_key",
    "payload",
}
_RELEASE_EXTERNAL_PAYLOAD_KEYS = {
    "arm_id",
    "arm_index",
    "case_id",
    "coordinate_key",
    "discovery_floor",
    "mechanism_id",
    "private_truth",
    "rung_index",
    "schema_version",
    "template_id",
    "template_version",
    "world_index",
}


class ReleaseVerificationError(ValueError):
    """A curated release artifact failed an integrity or runtime check."""


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseVerificationError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseVerificationError(f"{label} must be a JSON object: {path}")
    return value


def _expected_coordinates(record: Mapping[str, Any]) -> dict[str, Any]:
    runtime = runtime_for(record["task_family_id"])
    arm_index = 0 if record["tool_interface"] == "direct" else 1
    rung_index = int(record["workload_level"][1:])
    world_index = record["instance_index"] - 1
    member_key = (
        f"{runtime.implementation_id}/rung-{rung_index}/"
        f"world-{world_index}/arm-{arm_index}"
    )
    return {
        "case_id": runtime.implementation_id,
        "arm_index": arm_index,
        "rung_index": rung_index,
        "world_index": world_index,
        "member_key": member_key,
    }


def _check_instance_envelope(
    envelope: Mapping[str, Any],
    expected: Mapping[str, Any],
    label: str,
) -> None:
    if set(envelope) != _INSTANCE_FIELDS:
        raise ReleaseVerificationError(
            f"{label} fields do not match the strict frozen-instance schema"
        )
    if envelope.get("schema_version") != INSTANCE_SCHEMA_VERSION:
        raise ReleaseVerificationError(f"{label} has an unsupported schema")
    payload = envelope.get("payload")
    if not isinstance(payload, Mapping):
        raise ReleaseVerificationError(f"{label}.payload must be an object")
    if "config" in payload:
        raise ReleaseVerificationError(
            f"{label}.payload contains release-external metadata: config"
        )
    leaked = _release_external_metadata_path(payload)
    if leaked is not None:
        raise ReleaseVerificationError(
            f"{label}.payload contains release-external metadata: {leaked}"
        )
    _check_coordinates(envelope, expected, label)


def _release_external_metadata_path(
    value: Any, path: str = "payload"
) -> str | None:
    """Find known construction, identity, or secondary-score metadata."""

    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            nested_path = f"{path}.{key_text}"
            if (
                key_text in _RELEASE_EXTERNAL_PAYLOAD_KEYS
                or key_lower.startswith("construction_")
                or ("case" + "_score") in key_lower
            ):
                return nested_path
            leaked = _release_external_metadata_path(nested, nested_path)
            if leaked is not None:
                return leaked
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            leaked = _release_external_metadata_path(nested, f"{path}[{index}]")
            if leaked is not None:
                return leaked
    return None


def _check_coordinates(
    value: Mapping[str, Any], expected: Mapping[str, Any], label: str
) -> None:
    for field, expected_value in expected.items():
        if value.get(field) != expected_value:
            raise ReleaseVerificationError(
                f"{label}.{field} is inconsistent: expected {expected_value!r}"
            )


def verify_release(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Check manifest bindings, frozen bytes, and all final-decision runtimes."""

    try:
        manifest = load_public_manifest(manifest_path)
        root = repository_root(manifest_path)
    except ManifestError as exc:
        raise ReleaseVerificationError(str(exc)) from exc

    artifact_counts: dict[str, int] = {}
    for group in ("instances", "certificates", "prompts"):
        paths = artifact_paths(manifest, group)
        binding = manifest["artifact_integrity"][group]
        if len(paths) != binding["count"]:
            raise ReleaseVerificationError(f"{group} artifact count does not match")
        for relative_path in paths:
            path = resolve_artifact(root, relative_path)
            try:
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                expected = artifact_sha256(manifest, group, relative_path)
            except (ManifestError, OSError) as exc:
                raise ReleaseVerificationError(
                    f"cannot verify {relative_path}: {exc}"
                ) from exc
            if actual != expected:
                raise ReleaseVerificationError(
                    f"artifact digest does not match: {relative_path}"
                )
        artifact_counts[group] = len(paths)

    paired_certificates: dict[str, dict[str, tuple[str, int, str]]] = {}
    for record in manifest["algorithmic_worlds"]:
        world_id = record["algorithmic_world_id"]
        expected = _expected_coordinates(record)
        instance_path = resolve_artifact(root, record["instance_artifact"])
        certificate_path = resolve_artifact(root, record["certificate_artifact"])
        envelope = _read_object(instance_path, "instance")
        certificate = _read_object(certificate_path, "certificate")
        _check_instance_envelope(
            envelope,
            expected,
            f"{world_id}.instance",
        )
        try:
            validated_certificate = validate_exact_certificate(
                certificate,
                algorithmic_world_id=world_id,
                instance_sha256=artifact_sha256(
                    manifest, "instances", record["instance_artifact"]
                ),
                objective_sense=record["objective_sense"],
            )
        except (CertificateError, ManifestError) as exc:
            raise ReleaseVerificationError(f"{world_id}: {exc}") from exc

        paired_certificates.setdefault(record["hidden_instance_id"], {})[
            record["tool_interface"]
        ] = (
            validated_certificate["latent_instance_sha256"],
            validated_certificate["certified_optimum"],
            validated_certificate["objective_sense"],
        )

        state = load_frozen_state(instance_path)
        runtime = runtime_for(record["task_family_id"])
        session = WorldSession(runtime, state)
        environment, request = runtime.render_prompt(state)
        if not environment.strip() or not request.strip():
            raise ReleaseVerificationError(f"{world_id} rendered an empty prompt")
        if runtime.validate(state, None) != (False, None):
            raise ReleaseVerificationError(
                f"{world_id} checker must reject a missing final decision"
            )
        if len(session.tool_schemas) != len(runtime.query_tools) + 1:
            raise ReleaseVerificationError(f"{world_id} tool schema count is inconsistent")

    if len(paired_certificates) != 120:
        raise ReleaseVerificationError("release does not contain 120 hidden-instance pairs")
    for hidden_id, interfaces in paired_certificates.items():
        if set(interfaces) != {"direct", "mediated"}:
            raise ReleaseVerificationError(
                f"{hidden_id} is missing a Direct or Mediated certificate"
            )
        if interfaces["direct"] != interfaces["mediated"]:
            raise ReleaseVerificationError(
                f"{hidden_id} certificate pair has inconsistent latent binding or optimum"
            )

    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "status": "verified",
        "benchmark_manifest_sha256": manifest["manifest_sha256"],
        "world_count": 240,
        "artifacts": artifact_counts,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="algoworlds release",
        description="Verify the curated AlgoWorlds release artifacts.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    verify = subcommands.add_parser(
        "verify", help="verify frozen data, certificates, prompts, and runtimes"
    )
    verify.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    verify.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else list(argv))
    if args.command != "verify":
        raise AssertionError(f"unhandled command: {args.command}")
    try:
        report = verify_release(args.manifest)
    except (ManifestError, ReleaseVerificationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        counts = report["artifacts"]
        print(
            "verified 240 algorithmic worlds "
            f"({counts['instances']} instances, "
            f"{counts['certificates']} certificates, {counts['prompts']} prompts)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "ReleaseVerificationError",
    "VERIFICATION_SCHEMA_VERSION",
    "verify_release",
)
