from __future__ import annotations

import json

import pytest

from algoworlds.evaluate import run_evaluation
from algoworlds.providers import (
    ModelConfigurationError,
    ProviderFailure,
    ProviderRun,
    load_model_config,
)


class NoSubmissionTransport:
    def run(self, session, environment, request, *, max_turns):
        assert environment and request and session.tool_schemas
        return ProviderRun("no_final_decision", 1)


class FailedTransport:
    def run(self, session, environment, request, *, max_turns):
        raise ProviderFailure("endpoint unavailable")


def test_all_public_model_examples_are_single_safe_objects() -> None:
    assert load_model_config("examples/openai-responses.json").transport == "openai_responses"
    assert load_model_config("examples/openai-compatible.json").transport == "openai_chat_completions"
    assert load_model_config("examples/anthropic-messages.json").transport == "anthropic_messages"


def test_model_config_rejects_literal_credentials(tmp_path) -> None:
    path = tmp_path / "model.json"
    path.write_text(
        json.dumps(
            {
                "label": "unsafe",
                "transport": "openai_responses",
                "model": "model",
                "api_key_env": "OPENAI_API_KEY",
                "api_key": "secret",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModelConfigurationError, match="never api_key"):
        load_model_config(path)

    path.write_text(
        json.dumps(
            {
                "label": "unsafe-header",
                "transport": "openai_chat_completions",
                "model": "model",
                "api_key_env": "PROVIDER_API_KEY",
                "extra_parameters": {
                    "extra_headers": {"Authorization": "Bearer secret"}
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModelConfigurationError, match="api_key_env"):
        load_model_config(path)

    for sensitive_parameters in (
        {"access" + "_token": "value"},
        {"nested": {"client" + "_secret": "value"}},
        {"service" + "_credential": "value"},
    ):
        path.write_text(
            json.dumps(
                {
                    "label": "unsafe-extra",
                    "transport": "openai_chat_completions",
                    "model": "model",
                    "api_key_env": "PROVIDER_API_KEY",
                    "extra_parameters": sensitive_parameters,
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ModelConfigurationError, match="api_key_env"):
            load_model_config(path)


def test_subset_run_never_emits_an_official_summary(tmp_path) -> None:
    result = run_evaluation(
        model_config_path="examples/openai-responses.json",
        results_dir=tmp_path / "subset",
        algorithmic_world_ids=(
            "algoworlds/transit_routing/L1/instance-1/direct",
        ),
        transport=NoSubmissionTransport(),
    )
    assert result["status"] == "completed_subset"
    assert result["official_summary"] is None
    assert (tmp_path / "subset" / "partial-submissions.json").is_file()
    assert not (tmp_path / "subset" / "score.json").exists()


def test_provider_failure_blocks_results(tmp_path) -> None:
    result = run_evaluation(
        model_config_path="examples/openai-responses.json",
        results_dir=tmp_path / "failed",
        algorithmic_world_ids=(
            "algoworlds/transit_routing/L1/instance-1/direct",
        ),
        transport=FailedTransport(),
    )
    assert result["status"] == "blocked"
    assert result["infrastructure_error_count"] == 1
    assert not (tmp_path / "failed" / "partial-submissions.json").exists()


def test_dry_run_needs_no_credential_and_writes_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    destination = tmp_path / "dry"
    result = run_evaluation(
        model_config_path="examples/openai-responses.json",
        results_dir=destination,
        algorithmic_world_ids=(
            "algoworlds/transit_routing/L1/instance-1/direct",
        ),
        dry_run=True,
    )
    assert result["status"] == "dry_run"
    assert not destination.exists()
