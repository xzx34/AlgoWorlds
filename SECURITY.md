# Security Policy

## Reporting a vulnerability

Please report security issues privately through the repository's security
advisory feature. Do not open a public issue containing an active credential,
private endpoint, exploit, or sensitive evaluation artifact.

Include the affected revision, a minimal reproduction, expected impact, and any
temporary mitigation you have tested. Maintainers will acknowledge the report,
triage its scope, and coordinate disclosure after a fix is available.

## Credential handling

AlgoWorlds model profiles support `api_key_env` so credentials remain outside
committed configuration and provenance artifacts. Formal runs should use an
external secret manager or process environment and should never pass a literal
key through a committed model profile.

If a credential is committed or logged, revoke it at the provider before
removing it from the repository. Git history cleanup alone does not invalidate
an exposed secret.

## Supported release and supply chain

Security fixes target the latest `0.1.x` release. Continuous integration scans
the Python and website dependency graphs, reviews dependency changes, runs
CodeQL, and scans Git content for secrets. GitHub Actions are pinned to
immutable commits; version comments are informational and must be verified
against the upstream action repository before an update.

Release artifacts are checked against `release-policy.toml` after extraction.
Unexpected package members, archive links, path traversal, construction or
oracle code, and secondary-metric fields are release blockers.
