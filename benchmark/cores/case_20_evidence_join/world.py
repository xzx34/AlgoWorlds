"""Final-decision checker for Evidence-Joined Routing."""

from __future__ import annotations

from typing import Any

from .checker import checksum_parameters, join_sources
from .runtime_data import Instance


CASE_NAME = "case_20_evidence_join"


def validate(instance: Instance, submission: Any) -> tuple[bool, int | None]:
    if not isinstance(submission, dict):
        return False, None
    legal, objective, _ = validate_path(instance, submission.get("edges"))
    return legal, objective


def validate_path(instance: Instance, edges: Any) -> tuple[bool, int | None, str | None]:
    if not isinstance(edges, list) or not edges or any(not isinstance(item, str) for item in edges):
        return False, None, "edges must be a nonempty list of edge ids"
    if len(set(edges)) != len(edges):
        return False, None, "a path cannot repeat an edge"
    edge_index = {edge["edge_id"]: edge for edge in join_sources(instance)}
    if any(edge_id not in edge_index for edge_id in edges):
        return False, None, "unknown edge id"
    current = instance["public"]["source"]
    total = 0
    modulus, required_residue = checksum_parameters(instance)
    residue = 0
    for edge_id in edges:
        edge = edge_index[edge_id]
        if edge["tail"] != current:
            return False, None, "edges are not a connected directed path"
        current = edge["head"]
        total += edge["cost"]
        residue = (residue + edge["residue_delta"]) % modulus
    if current != instance["public"]["destination"]:
        return False, None, "path does not reach the destination"
    if residue != required_residue:
        return False, None, "path residue does not equal the required residue"
    return True, total, None
