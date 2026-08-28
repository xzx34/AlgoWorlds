from __future__ import annotations

import json
import re
from collections import defaultdict

from algoworlds.manifest import load_public_manifest, repository_root, resolve_artifact
from algoworlds.release import verify_release
from algoworlds.runtime import WorldSession, load_frozen_state, runtime_for


def test_release_verification_checks_every_frozen_artifact() -> None:
    report = verify_release()
    assert report["status"] == "verified"
    assert report["world_count"] == 240
    assert report["artifacts"] == {
        "instances": 240,
        "certificates": 240,
        "prompts": 20,
    }


def test_all_worlds_render_tools_and_reject_missing_decisions() -> None:
    manifest = load_public_manifest()
    root = repository_root()
    placeholder = re.compile(r"<[a-z][a-z0-9_]*>")
    for record in manifest["algorithmic_worlds"]:
        runtime = runtime_for(record["task_family_id"])
        state = load_frozen_state(resolve_artifact(root, record["instance_artifact"]))
        environment, request = runtime.render_prompt(state)
        assert not placeholder.search(environment + request)
        session = WorldSession(runtime, state)
        assert {item["function"]["name"] for item in session.tool_schemas} == set(
            (*runtime.query_tools, runtime.submit_tool)
        )
        assert runtime.validate(state, None) == (False, None)


def test_frozen_payloads_exclude_release_external_metadata() -> None:
    manifest = load_public_manifest()
    root = repository_root()
    forbidden = {
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

    def keys(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield key
                yield from keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from keys(nested)

    for record in manifest["algorithmic_worlds"]:
        state = load_frozen_state(resolve_artifact(root, record["instance_artifact"]))
        assert "config" not in state
        for key in keys(state):
            assert key not in forbidden
            assert not key.lower().startswith("construction_")
            assert ("case" + "_score") not in key.lower()


def test_exact_certificates_are_strict_and_pair_the_120_hidden_instances() -> None:
    manifest = load_public_manifest()
    root = repository_root()
    pairs = defaultdict(dict)
    expected_fields = {
        "schema_version",
        "algorithmic_world_id",
        "instance_sha256",
        "latent_instance_sha256",
        "objective_sense",
        "certified_optimum",
    }
    for record in manifest["algorithmic_worlds"]:
        certificate = json.loads(
            resolve_artifact(root, record["certificate_artifact"]).read_text(
                encoding="utf-8"
            )
        )
        assert set(certificate) == expected_fields
        assert certificate["schema_version"] == "algoworlds_exact_certificate/1"
        pairs[record["hidden_instance_id"]][record["tool_interface"]] = (
            certificate["latent_instance_sha256"],
            certificate["certified_optimum"],
            certificate["objective_sense"],
        )
    assert len(pairs) == 120
    assert all(set(pair) == {"direct", "mediated"} for pair in pairs.values())
    assert all(pair["direct"] == pair["mediated"] for pair in pairs.values())
