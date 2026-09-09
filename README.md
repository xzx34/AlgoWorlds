# AlgoWorlds

AlgoWorlds evaluates whether language-model agents can acquire information
through tools and turn it into globally optimal decisions.

**Weixin AI**

[Project page](https://xzx34.github.io/AlgoWorlds/) ·
[Paper (arXiv)](https://arxiv.org/abs/2608.29397) ·
[Code and dataset](https://github.com/xzx34/AlgoWorlds)

## Curated release

This repository contains the selected benchmark release used for public model
evaluation:

- 10 task families;
- 4 workload levels (`L1`–`L4`);
- 3 hidden instances per family and level;
- Direct and Mediated tool interfaces for every hidden instance;
- 120 hidden instances and 240 algorithmic worlds in total.

It includes 240 interface-specific frozen instance artifacts representing the
120 paired hidden instances, 240 world-bound verification certificates, 20
prompt files, model-facing tools, final-decision checkers, and a public runner.
It does not include data construction, instance generation, admission,
oracle-solving, internal infrastructure, or paper-evaluation sessions.

The ten task families are Transit Routing, Basket Assembly, Station Siting,
Authorization Planning, Series Portfolio, Machine Layout, Sequential Matching,
Fleet Dispatch, Evidence-Joined Routing, and Migration Portfolio.

## Official metric

The paper reports three final-decision metrics and two trajectory diagnostics.
This curated release deliberately exposes only the paper's primary metric:
**Exact optimality**. A world receives `1` if and only if all three conditions
hold:

1. the model made a structured final decision;
2. the task-family checker accepts that decision as feasible;
3. its integer objective equals the certified optimum exactly.

There is no floating-point tolerance. Missing, malformed, infeasible, or
suboptimal decisions receive `0`.

An official score is computed from exactly one submission for each of the 240
algorithmic-world IDs in one complete trial. Missing, duplicate, unknown, or
manifest-mismatched entries are rejected. The paper reports the mean and sample
standard deviation across three independently executed trials. The public
scorer returns one trial summary at a time, so those trials must use separate
result directories and be summarized outside this package.

## Install and verify

AlgoWorlds supports Python 3.11 and 3.12 on Linux and macOS.

```bash
python -m pip install -e .
algoworlds release verify
algoworlds worlds list --task-family transit_routing --workload-level L1
```

`release verify` checks all frozen instance, certificate, and prompt bytes and
loads every public runtime. It does not replay a generator or solver.

## Evaluate a model

Three public transports are supported:

- OpenAI Responses;
- OpenAI-compatible Chat Completions;
- Anthropic Messages (install the optional `anthropic` dependency).

Copy one JSON object from `examples/`, set its model ID, and keep the credential
in the environment variable named by `api_key_env`.

```bash
cp examples/openai-responses.json model.local.json
export OPENAI_API_KEY='...'

algoworlds evaluate \
  --model-config model.local.json \
  --results-dir results/trial-1 \
  --dry-run
```

Remove `--dry-run` to start the complete 240-world evaluation. Use
`--algorithmic-world ID` one or more times for a smoke-test subset. Subsets
produce `partial-submissions.json` but never an official aggregate. A completed
full run produces `submissions.json` and `score.json`.

Provider authentication, network, and endpoint failures block the official
summary. A normal model response that ends without the terminal submission tool
is a model outcome and receives `0` for that world. Use `--resume` with the same
configuration to retain completed worlds and retry interrupted ones.

## Score existing submissions

```bash
algoworlds score submissions.json --output score.json
```

The submission file is bound to the bundled manifest digest:

```json
{
  "schema_version": "algoworlds_submissions/1",
  "benchmark_manifest_sha256": "<digest from algoworlds release verify --json>",
  "entries": [
    {
      "algorithmic_world_id": "algoworlds/transit_routing/L1/instance-1/direct",
      "final_decision": null
    }
  ]
}
```

An official file contains all 240 entries. The summary reports only
`world_count`, `exact_optimal_count`, `exact_optimality_percent`, and the
per-world Exact-optimality flags, together with schema and manifest bindings.

## Python API

```python
from algoworlds import (
    iter_algorithmic_worlds,
    load_public_manifest,
    score_decision,
    score_trial,
)

assert len(tuple(iter_algorithmic_worlds())) == 240
manifest = load_public_manifest()
flag = score_decision(
    "algoworlds/transit_routing/L1/instance-1/direct",
    final_decision=None,
)
assert flag == 0
```

## Repository layout

```text
algoworlds/       public identities, runner, verifier, and Exact-optimality scorer
benchmark/        compact release manifest
benchmark/cores/  frozen artifacts and minimal task-family runtimes
examples/         sanitized single-model configurations
tests/            curated release and runtime tests
website/          project page
```

The code is licensed under Apache-2.0. Third-party visual assets retain the
notices recorded in the website asset inventory.

## License and attribution

Software and documentation are licensed under the Apache License 2.0 in
`LICENSE`. The frozen instance, certificate, and prompt artifacts under
`benchmark/cores/*/instances/` and `benchmark/cores/*/prompts/` are licensed
under Creative Commons Attribution 4.0 International in `DATA_LICENSE`.

When redistributing or adapting those artifacts, attribute **Weixin AI**, link
to this repository and the CC BY 4.0 license, and indicate changes. The Weixin
name and mark, third-party marks, and the paper-derived website figure are not
licensed under Apache-2.0 or CC BY 4.0. See `NOTICE` for the precise boundary.
