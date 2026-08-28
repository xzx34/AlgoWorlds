# Contributing to AlgoWorlds

AlgoWorlds welcomes reproducibility fixes, provider adapters, documentation,
tests, and carefully reviewed runtime improvements.

## Development setup

Use Python 3.11 or 3.12 and install the development dependencies:

```bash
python -m pip install -e '.[anthropic,dev]'
python -m pytest -q
algoworlds release verify
python scripts/check_public_terminology.py
python scripts/check_release_boundary.py source
```

Run focused tests for every subsystem you modify.

## Scientific compatibility

The bundled manifest binds 240 instance files, 240 certificates, and 20 prompt
files. Do not rewrite these frozen artifacts in place. A scientifically changed
benchmark requires a new release identity and new integrity bindings.

Exact optimality is the only public metric. Scoring changes require an explicit
scientific decision and golden tests. Evaluation-runtime refactors must retain
native structured tool use, cost-budget enforcement, binding terminal-call
semantics, and the distinction between model outcomes and infrastructure
failures.

The website may statically display the paper's five reported measures. That
presentation exception must not add secondary-metric code, schemas, or run
artifacts to the evaluator or packaged benchmark.

## Release boundary

`release-policy.toml` is a positive allowlist for the history-free public
source tree and built archives. Do not broaden it with an unreviewed directory
wildcard. Release CI builds both wheel and sdist, extracts them into temporary
directories, and rejects every path outside the package allowlist.

Frozen instances, certificates, and prompts are CC BY 4.0 data artifacts;
source code and documentation are Apache-2.0. Preserve `LICENSE`,
`DATA_LICENSE`, and `NOTICE` in source and binary distributions.

## Public terminology

Public Python names, command help, schemas, examples, and documentation use:

- task family;
- workload level `L1`–`L4`;
- hidden-instance index `1`–`3`;
- Direct or Mediated tool interface;
- hidden instance and algorithmic world;
- evaluation and trial.

Implementation coordinates may appear in frozen paths and runtime internals.
Public commands, schemas, examples, and prose must use the public names above.

## Security and data handling

Never commit credentials, private endpoints, internal filesystem paths,
cluster configuration, raw model sessions, or unpublished result roots.
Public model profiles name credential environment variables with
`api_key_env` and use sanitized example endpoints.

## Style

- Use English for source code, comments, tests, configuration, and public documentation.
- Use `Weixin AI` as the only organization identity; do not list individual authors.
- Keep provider-specific behavior behind adapters and reuse the common runtime.
- Preserve infrastructure failures as auditable artifacts instead of model scores.
- Add deterministic tests for every behavior change.
