from __future__ import annotations

from algoworlds.identity import (
    identity_from_algorithmic_world_id,
    iter_algorithmic_worlds,
)
from algoworlds.manifest import (
    artifact_paths,
    artifact_sha256,
    load_public_manifest,
    load_raw_manifest,
)


def test_public_roster_is_a_bijective_240_world_grid() -> None:
    identities = tuple(iter_algorithmic_worlds())
    ids = [identity.algorithmic_world_id for identity in identities]
    assert len(ids) == len(set(ids)) == 240
    assert all(
        identity_from_algorithmic_world_id(world_id).algorithmic_world_id == world_id
        for world_id in ids
    )


def test_curated_manifest_expands_and_binds_only_release_artifacts() -> None:
    raw = load_raw_manifest()
    public = load_public_manifest()
    assert raw["schema_version"] == "algoworlds_benchmark_manifest/2"
    assert raw["benchmark_id"] == "algoworlds"
    assert raw["affiliation"] == "Weixin AI"
    assert raw["release_scope"]["official_metric"] == "exact_optimality"
    assert raw["release"] == {
        "release_id": "algoworlds-curated-exact-240-v1",
        "source_snapshot_digest": (
            "sha256:093e12db11bf1bd0eaa944036d1a16dbc8a434d5e181df6677bbd6c1257d6c63"
        ),
    }
    assert "source" not in raw
    assert len(public["algorithmic_worlds"]) == 240
    for group, expected_count in {
        "instances": 240,
        "certificates": 240,
        "prompts": 20,
    }.items():
        paths = artifact_paths(raw, group)
        assert len(paths) == expected_count
        assert set(paths) == set(raw["artifact_integrity"][group]["files"])
        assert all(len(artifact_sha256(raw, group, path)) == 64 for path in paths)
