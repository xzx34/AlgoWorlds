"""Strict Exact-optimality certificates for the curated release."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


EXACT_CERTIFICATE_SCHEMA_VERSION = "algoworlds_exact_certificate/1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = {
    "schema_version",
    "algorithmic_world_id",
    "instance_sha256",
    "latent_instance_sha256",
    "objective_sense",
    "certified_optimum",
}


class CertificateError(ValueError):
    """An Exact-optimality certificate is malformed or inconsistently bound."""


def validate_exact_certificate(
    payload: Mapping[str, Any],
    *,
    algorithmic_world_id: str,
    instance_sha256: str,
    objective_sense: str,
) -> dict[str, Any]:
    """Validate one certificate and its world, instance, and objective bindings."""

    if not isinstance(payload, Mapping) or set(payload) != _FIELDS:
        raise CertificateError("certificate fields do not match the strict schema")
    if payload.get("schema_version") != EXACT_CERTIFICATE_SCHEMA_VERSION:
        raise CertificateError("unsupported certificate schema")
    if payload.get("algorithmic_world_id") != algorithmic_world_id:
        raise CertificateError("certificate algorithmic-world ID does not match")
    if payload.get("instance_sha256") != instance_sha256:
        raise CertificateError("certificate does not bind the instance bytes")
    if payload.get("objective_sense") != objective_sense:
        raise CertificateError("certificate objective sense does not match")
    for field in (
        "instance_sha256",
        "latent_instance_sha256",
    ):
        value = payload.get(field)
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            raise CertificateError(f"certificate {field} must be a SHA-256 digest")
    optimum = payload.get("certified_optimum")
    if isinstance(optimum, bool) or not isinstance(optimum, int):
        raise CertificateError("certificate optimum must be an integer")
    return dict(payload)


__all__ = (
    "CertificateError",
    "EXACT_CERTIFICATE_SCHEMA_VERSION",
    "validate_exact_certificate",
)
