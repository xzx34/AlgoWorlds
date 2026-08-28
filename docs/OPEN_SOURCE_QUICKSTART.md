# AlgoWorlds quickstart

This guide covers the curated 240-world release, its public model runner, and
the paper's primary metric, Exact optimality. The paper also reports two
secondary final-decision metrics and two trajectory diagnostics; they are not
part of this selected public scorer.

## 1. Install

Use Python 3.11 or 3.12 on Linux or macOS.

```bash
python -m pip install -e .
```

For Anthropic Messages or local development:

```bash
python -m pip install -e '.[anthropic]'
python -m pip install -e '.[dev]'
```

## 2. Verify the release

```bash
algoworlds release verify
algoworlds release verify --json
```

Verification checks the compact release manifest, 240 interface-specific
instance files representing 120 paired hidden instances, all 240 world-bound
certificates, all 20 prompt files, and every model-facing runtime. No data
generator or exact solver is included or replayed.

## 3. Inspect the worlds

```bash
algoworlds worlds list
algoworlds worlds list \
  --task-family fleet_dispatch \
  --workload-level L2 \
  --instance-index 2 \
  --tool-interface mediated \
  --json
```

Public IDs are one-indexed:

```text
algoworlds/fleet_dispatch/L2/instance-2
algoworlds/fleet_dispatch/L2/instance-2/mediated
```

## 4. Configure one model

Each `evaluate` invocation accepts one JSON model object. Start from the
matching example:

```bash
cp examples/openai-responses.json model.local.json
export OPENAI_API_KEY='...'
```

Available `transport` values are:

| Transport | Endpoint contract | Example |
|---|---|---|
| `openai_responses` | OpenAI Responses | `examples/openai-responses.json` |
| `openai_chat_completions` | OpenAI-compatible Chat Completions | `examples/openai-compatible.json` |
| `anthropic_messages` | Anthropic Messages | `examples/anthropic-messages.json` |

Profiles contain `api_key_env`, never a literal credential. Provider-specific
request controls may be placed in `extra_parameters`; core fields such as the
model, messages, tools, endpoint, and credential cannot be overridden there.

## 5. Dry-run and evaluate

A dry run verifies the release, profile, prompt rendering, selection, and tool
schemas without reading the credential or contacting a model endpoint.

```bash
algoworlds evaluate \
  --model-config model.local.json \
  --results-dir results/smoke \
  --algorithmic-world algoworlds/transit_routing/L1/instance-1/direct \
  --dry-run
```

Remove `--dry-run` to execute the selected world. Omit
`--algorithmic-world` to run the complete trial:

```bash
algoworlds evaluate \
  --model-config model.local.json \
  --results-dir results/trial-1 \
  --concurrency 4
```

The runner uses native structured tool calls. Query tools consume the frozen
per-world cost budget; the terminal submission tool does not. The first
successfully executed terminal call binds the final decision.

For a complete successful run, the result directory contains:

```text
run.json
worlds/*.json
submissions.json
score.json
```

A subset instead receives `partial-submissions.json` and no official score.
Use `--resume` only with the identical model, manifest, world selection, and
runtime options. Completed worlds are reused; interrupted worlds are retried.

Authentication, network, provider, and endpoint failures leave the full run
blocked and prevent `score.json`. If the model itself finishes, reaches the
turn cap, or exhausts its response without a final decision, the run is valid
and that world receives `0`.

## 6. Score a complete submission file

```bash
algoworlds score submissions.json --output score.json
```

Official scoring requires exactly one entry for every canonical world ID and
the exact `benchmark_manifest_sha256` reported by `release verify --json`.
Order does not matter; missing, duplicate, unknown, or mismatched entries are
rejected.

The scorer returns `1` only when a structured final decision is feasible and
its integer objective equals the certificate's exact optimum. There is no
floating tolerance. It reports one 240-world Exact-optimality percentage at a
time. The paper's reported mean and sample standard deviation come from three
separately executed 240-world trials; cross-trial aggregation is intentionally
outside this package.

## 7. Python API

```python
from algoworlds import load_public_manifest, score_decision, score_trial

manifest = load_public_manifest()
assert manifest["dimensions"]["algorithmic_worlds"] == 240

flag = score_decision(
    "algoworlds/fleet_dispatch/L2/instance-2/mediated",
    {"assignment": {}},
)
assert flag in (0, 1)
```

The evaluator and frozen artifacts support only Exact optimality. The public
release deliberately excludes instance construction, generators, oracles,
internal execution systems, historical campaigns, secondary-metric
implementations, and trajectory-diagnostic implementations. The project page
is the sole exception: it statically presents all five paper measures for
scientific context, but contains no public implementation or per-run output for
the other four measures.

Software and documentation use Apache-2.0. Frozen instances, certificates, and
prompts use CC BY 4.0 with attribution to Weixin AI. See `NOTICE` and
`DATA_LICENSE` before redistribution.
