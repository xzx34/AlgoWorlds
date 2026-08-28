from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

import algoworlds.scoring as scoring
from algoworlds.manifest import DEFAULT_MANIFEST_PATH, load_public_manifest
from algoworlds.scoring import ScoringError, score_decision, score_trial


def _empty_trial() -> dict:
    manifest = load_public_manifest()
    return {
        "schema_version": "algoworlds_submissions/1",
        "benchmark_manifest_sha256": manifest["manifest_sha256"],
        "entries": [
            {
                "algorithmic_world_id": world["algorithmic_world_id"],
                "final_decision": None,
            }
            for world in manifest["algorithmic_worlds"]
        ],
    }


def test_complete_trial_reports_only_exact_optimality() -> None:
    summary = score_trial(_empty_trial())
    assert summary["world_count"] == 240
    assert summary["exact_optimal_count"] == 0
    assert summary["exact_optimality_percent"] == 0.0
    assert len(summary["worlds"]) == 240
    assert set(summary) == {
        "schema_version",
        "benchmark_manifest_sha256",
        "world_count",
        "exact_optimal_count",
        "exact_optimality_percent",
        "worlds",
    }
    assert all(set(item) == {"algorithmic_world_id", "exact_optimality"} for item in summary["worlds"])


def test_official_trial_rejects_missing_duplicate_and_manifest_mismatch() -> None:
    missing = _empty_trial()
    missing["entries"].pop()
    with pytest.raises(ScoringError, match="requires all 240"):
        score_trial(missing)

    duplicate = _empty_trial()
    duplicate["entries"][-1] = duplicate["entries"][0]
    with pytest.raises(ScoringError, match="duplicate"):
        score_trial(duplicate)

    mismatch = _empty_trial()
    mismatch["benchmark_manifest_sha256"] = "0" * 64
    with pytest.raises(ScoringError, match="digest"):
        score_trial(mismatch)


def test_exact_comparison_is_integer_and_has_no_tolerance(monkeypatch) -> None:
    record = {"algorithmic_world_id": "world", "task_family_id": "family"}
    monkeypatch.setattr(
        scoring,
        "_certified_optimum",
        lambda record, root, manifest: ({}, 10),
    )

    class Runtime:
        def __init__(self, result):
            self.result = result

        def validate(self, state, decision):
            return self.result

    monkeypatch.setattr(scoring, "runtime_for", lambda family: Runtime((True, 10)))
    assert scoring._score_record(record, {"decision": 1}, Path("."), {}) == 1
    monkeypatch.setattr(scoring, "runtime_for", lambda family: Runtime((True, 9)))
    assert scoring._score_record(record, {"decision": 1}, Path("."), {}) == 0
    monkeypatch.setattr(scoring, "runtime_for", lambda family: Runtime((False, 10)))
    assert scoring._score_record(record, {"decision": 1}, Path("."), {}) == 0
    monkeypatch.setattr(scoring, "runtime_for", lambda family: Runtime((True, 10.0)))
    with pytest.raises(ScoringError, match="non-integer"):
        scoring._score_record(record, {"decision": 1}, Path("."), {})


def test_public_single_world_scorer_treats_missing_decision_as_zero() -> None:
    assert (
        score_decision(
            "algoworlds/transit_routing/L1/instance-1/direct", None
        )
        == 0
    )


def _isolated_world(tmp_path: Path) -> tuple[Path, dict]:
    release_root = tmp_path / "release"
    manifest_path = release_root / "benchmark" / "MANIFEST.json"
    manifest_path.parent.mkdir(parents=True)
    shutil.copy2(DEFAULT_MANIFEST_PATH, manifest_path)
    manifest = load_public_manifest(manifest_path)
    record = manifest["algorithmic_worlds"][0]
    source_root = DEFAULT_MANIFEST_PATH.parent.parent
    for field in ("instance_artifact", "certificate_artifact"):
        relative_path = record[field]
        destination = release_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative_path, destination)
    return manifest_path, record


@pytest.mark.parametrize(
    ("artifact_field", "message"),
    (
        ("instance_artifact", "instance bytes"),
        ("certificate_artifact", "certificate bytes"),
    ),
)
def test_single_world_scorer_rejects_tampered_artifact_bytes(
    tmp_path: Path, artifact_field: str, message: str
) -> None:
    manifest_path, record = _isolated_world(tmp_path)
    artifact = manifest_path.parent.parent / record[artifact_field]
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    with pytest.raises(ScoringError, match=message):
        score_decision(record["algorithmic_world_id"], None, manifest_path=manifest_path)


def test_single_world_scorer_rejects_certificate_schema_expansion(
    tmp_path: Path,
) -> None:
    manifest_path, record = _isolated_world(tmp_path)
    release_root = manifest_path.parent.parent
    certificate_path = release_root / record["certificate_artifact"]
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    certificate["secondary_metric"] = 1
    certificate_path.write_text(
        json.dumps(certificate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_integrity"]["certificates"]["files"][
        record["certificate_artifact"]
    ] = hashlib.sha256(certificate_path.read_bytes()).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(ScoringError, match="strict schema"):
        score_decision(record["algorithmic_world_id"], None, manifest_path=manifest_path)


def test_single_world_scorer_rejects_tampered_manifest_binding(
    tmp_path: Path,
) -> None:
    manifest_path, record = _isolated_world(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_integrity"]["instances"]["files"][
        record["instance_artifact"]
    ] = "0" * 64
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(ScoringError, match="instance bytes"):
        score_decision(record["algorithmic_world_id"], None, manifest_path=manifest_path)
