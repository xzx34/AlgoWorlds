"""Public model transports for the curated AlgoWorlds runner."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from algoworlds.runtime import WorldSession


TRANSPORTS = (
    "openai_responses",
    "openai_chat_completions",
    "anthropic_messages",
)
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RESERVED_PARAMETERS = {
    "api_key",
    "base_url",
    "input",
    "instructions",
    "messages",
    "model",
    "previous_response_id",
    "system",
    "tools",
}
_SENSITIVE_KEYS = {
    "api-key",
    "api_key",
    "access-token",
    "access_token",
    "authorization",
    "client-secret",
    "client_secret",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "default_headers",
    "extra_headers",
    "password",
    "proxy-authorization",
    "refresh-token",
    "refresh_token",
    "secret",
    "token",
    "x-api-key",
}


class ModelConfigurationError(ValueError):
    """A public model profile is malformed or unsafe."""


class ProviderFailure(RuntimeError):
    """Authentication, network, endpoint, or provider protocol failure."""


@dataclass(frozen=True, slots=True)
class ModelConfig:
    label: str
    transport: str
    model: str
    api_key_env: str
    base_url: str | None = None
    max_output_tokens: int = 16384
    temperature: float | None = None
    reasoning_effort: str | None = None
    extra_parameters: Mapping[str, Any] = field(default_factory=dict)

    def public_record(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "transport": self.transport,
            "model": self.model,
            "api_key_env": self.api_key_env,
            "base_url": self.base_url,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "reasoning_effort": self.reasoning_effort,
            "extra_parameters": dict(self.extra_parameters),
        }


@dataclass(frozen=True, slots=True)
class ProviderRun:
    termination: str
    turns: int


class Transport(Protocol):
    def run(
        self,
        session: WorldSession,
        environment: str,
        request: str,
        *,
        max_turns: int,
    ) -> ProviderRun: ...


def _sensitive_parameter_path(value: Any, prefix: str = "extra_parameters") -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key)
            path = f"{prefix}.{name}"
            normalized = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
            if (
                name.casefold() in _SENSITIVE_KEYS
                or normalized in _SENSITIVE_KEYS
                or normalized.endswith(
                    (
                        "_api_key",
                        "_credential",
                        "_credentials",
                        "_password",
                        "_secret",
                        "_token",
                    )
                )
                or normalized.endswith("_headers")
            ):
                return path
            found = _sensitive_parameter_path(child, path)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _sensitive_parameter_path(child, f"{prefix}[{index}]")
            if found is not None:
                return found
    return None


def load_model_config(path: str | Path) -> ModelConfig:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelConfigurationError(f"cannot read model config {source}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ModelConfigurationError("model config must be one JSON object")
    if "api_key" in raw:
        raise ModelConfigurationError("store credentials in api_key_env, never api_key")
    required = ("label", "transport", "model", "api_key_env")
    for field_name in required:
        if not isinstance(raw.get(field_name), str) or not raw[field_name].strip():
            raise ModelConfigurationError(f"{field_name} must be a nonempty string")
    if raw["transport"] not in TRANSPORTS:
        raise ModelConfigurationError(
            "transport must be one of " + ", ".join(TRANSPORTS)
        )
    if _ENV_NAME.fullmatch(raw["api_key_env"]) is None:
        raise ModelConfigurationError("api_key_env is not a valid environment name")
    base_url = raw.get("base_url")
    if base_url is not None and (not isinstance(base_url, str) or not base_url.strip()):
        raise ModelConfigurationError("base_url must be a nonempty string when set")
    max_tokens = raw.get("max_output_tokens", 16384)
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise ModelConfigurationError("max_output_tokens must be a positive integer")
    temperature = raw.get("temperature")
    if temperature is not None and (
        isinstance(temperature, bool) or not isinstance(temperature, (int, float))
    ):
        raise ModelConfigurationError("temperature must be numeric when set")
    effort = raw.get("reasoning_effort")
    if effort is not None and (
        not isinstance(effort, str) or effort not in {"minimal", "low", "medium", "high"}
    ):
        raise ModelConfigurationError(
            "reasoning_effort must be minimal, low, medium, or high"
        )
    extras = raw.get("extra_parameters", {})
    if not isinstance(extras, Mapping):
        raise ModelConfigurationError("extra_parameters must be an object")
    forbidden = sorted(_RESERVED_PARAMETERS.intersection(extras))
    if forbidden:
        raise ModelConfigurationError(
            "extra_parameters cannot override: " + ", ".join(forbidden)
        )
    sensitive_path = _sensitive_parameter_path(extras)
    if sensitive_path is not None:
        raise ModelConfigurationError(
            f"credentials are not allowed in {sensitive_path}; use api_key_env"
        )
    return ModelConfig(
        label=raw["label"].strip(),
        transport=raw["transport"],
        model=raw["model"].strip(),
        api_key_env=raw["api_key_env"],
        base_url=base_url.strip() if isinstance(base_url, str) else None,
        max_output_tokens=max_tokens,
        temperature=float(temperature) if temperature is not None else None,
        reasoning_effort=effort,
        extra_parameters=dict(extras),
    )


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _dump_block(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    method = getattr(value, "model_dump", None)
    if callable(method):
        result = method(exclude_none=True)
        if isinstance(result, dict):
            return result
    raise ProviderFailure("provider returned an unsupported content block")


def _tool_arguments(raw: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if isinstance(raw, Mapping):
        return dict(raw), None
    if not isinstance(raw, str):
        return None, {"error": "tool arguments must be a JSON object"}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, {"error": f"tool arguments are not valid JSON: {exc.msg}"}
    if not isinstance(value, dict):
        return None, {"error": "tool arguments must decode to a JSON object"}
    return value, None


def _execute(session: WorldSession, name: Any, raw_args: Any) -> dict[str, Any]:
    if not isinstance(name, str) or not name:
        return {"error": "tool name must be a nonempty string"}
    arguments, error = _tool_arguments(raw_args)
    return error if error is not None else session.call(name, arguments or {})


def _api_key(config: ModelConfig) -> str:
    value = os.environ.get(config.api_key_env)
    if not value:
        raise ModelConfigurationError(
            f"environment variable {config.api_key_env} is not set"
        )
    return value


def _responses_tools(schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for schema in schemas:
        function = schema["function"]
        result.append(
            {
                "type": "function",
                "name": function["name"],
                "description": function.get("description", ""),
                "parameters": function["parameters"],
            }
        )
    return result


def _anthropic_tools(schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": schema["function"]["name"],
            "description": schema["function"].get("description", ""),
            "input_schema": schema["function"]["parameters"],
        }
        for schema in schemas
    ]


class OpenAIResponsesTransport:
    def __init__(self, config: ModelConfig, timeout: float) -> None:
        from openai import OpenAI

        options: dict[str, Any] = {
            "api_key": _api_key(config),
            "timeout": timeout,
        }
        if config.base_url:
            options["base_url"] = config.base_url
        self.client = OpenAI(**options)
        self.config = config

    def run(
        self,
        session: WorldSession,
        environment: str,
        request: str,
        *,
        max_turns: int,
    ) -> ProviderRun:
        previous_response_id: str | None = None
        next_input: Any = [{"role": "user", "content": request}]
        tools = _responses_tools(session.tool_schemas)
        for turn in range(1, max_turns + 1):
            parameters: dict[str, Any] = {
                "model": self.config.model,
                "input": next_input,
                "instructions": environment,
                "tools": tools,
                "max_output_tokens": self.config.max_output_tokens,
                "store": True,
                **self.config.extra_parameters,
            }
            if previous_response_id is not None:
                parameters["previous_response_id"] = previous_response_id
            if self.config.temperature is not None:
                parameters["temperature"] = self.config.temperature
            if self.config.reasoning_effort is not None:
                parameters["reasoning"] = {"effort": self.config.reasoning_effort}
            try:
                response = self.client.responses.create(**parameters)
            except Exception as exc:
                raise ProviderFailure(f"OpenAI Responses request failed: {exc}") from exc
            calls = [
                item
                for item in (_field(response, "output", []) or [])
                if _field(item, "type") == "function_call"
            ]
            if not calls:
                return ProviderRun("no_final_decision", turn)
            outputs = []
            for call in calls:
                call_id = _field(call, "call_id") or _field(call, "id")
                if not isinstance(call_id, str):
                    raise ProviderFailure("Responses function call has no call_id")
                result = _execute(
                    session, _field(call, "name"), _field(call, "arguments", "{}")
                )
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result, separators=(",", ":")),
                    }
                )
                if session.final_decision is not None:
                    return ProviderRun("submitted", turn)
            previous_response_id = _field(response, "id")
            if not isinstance(previous_response_id, str):
                raise ProviderFailure("Responses result has no response id")
            next_input = outputs
        return ProviderRun("max_turns", max_turns)


class OpenAIChatCompletionsTransport:
    def __init__(self, config: ModelConfig, timeout: float) -> None:
        from openai import OpenAI

        options: dict[str, Any] = {
            "api_key": _api_key(config),
            "timeout": timeout,
        }
        if config.base_url:
            options["base_url"] = config.base_url
        self.client = OpenAI(**options)
        self.config = config

    def run(
        self,
        session: WorldSession,
        environment: str,
        request: str,
        *,
        max_turns: int,
    ) -> ProviderRun:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": environment},
            {"role": "user", "content": request},
        ]
        for turn in range(1, max_turns + 1):
            parameters: dict[str, Any] = {
                "model": self.config.model,
                "messages": messages,
                "tools": session.tool_schemas,
                "max_tokens": self.config.max_output_tokens,
                **self.config.extra_parameters,
            }
            if self.config.temperature is not None:
                parameters["temperature"] = self.config.temperature
            if self.config.reasoning_effort is not None:
                parameters["reasoning_effort"] = self.config.reasoning_effort
            try:
                response = self.client.chat.completions.create(**parameters)
            except Exception as exc:
                raise ProviderFailure(f"Chat Completions request failed: {exc}") from exc
            choices = _field(response, "choices", []) or []
            if not choices:
                raise ProviderFailure("Chat Completions returned no choices")
            message = _field(choices[0], "message")
            calls = _field(message, "tool_calls", []) or []
            assistant: dict[str, Any] = {
                "role": "assistant",
                "content": _field(message, "content"),
            }
            if calls:
                assistant["tool_calls"] = [
                    {
                        "id": _field(call, "id"),
                        "type": "function",
                        "function": {
                            "name": _field(_field(call, "function"), "name"),
                            "arguments": _field(
                                _field(call, "function"), "arguments", "{}"
                            ),
                        },
                    }
                    for call in calls
                ]
            messages.append(assistant)
            if not calls:
                return ProviderRun("no_final_decision", turn)
            for call in calls:
                call_id = _field(call, "id")
                function = _field(call, "function")
                if not isinstance(call_id, str):
                    raise ProviderFailure("Chat Completions tool call has no id")
                result = _execute(
                    session,
                    _field(function, "name"),
                    _field(function, "arguments", "{}"),
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result, separators=(",", ":")),
                    }
                )
                if session.final_decision is not None:
                    return ProviderRun("submitted", turn)
        return ProviderRun("max_turns", max_turns)


class AnthropicMessagesTransport:
    def __init__(self, config: ModelConfig, timeout: float) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ModelConfigurationError(
                "Anthropic transport requires `pip install -e '.[anthropic]'`"
            ) from exc
        options: dict[str, Any] = {
            "api_key": _api_key(config),
            "timeout": timeout,
        }
        if config.base_url:
            options["base_url"] = config.base_url
        self.client = Anthropic(**options)
        self.config = config

    def run(
        self,
        session: WorldSession,
        environment: str,
        request: str,
        *,
        max_turns: int,
    ) -> ProviderRun:
        messages: list[dict[str, Any]] = [{"role": "user", "content": request}]
        tools = _anthropic_tools(session.tool_schemas)
        for turn in range(1, max_turns + 1):
            parameters: dict[str, Any] = {
                "model": self.config.model,
                "system": environment,
                "messages": messages,
                "tools": tools,
                "max_tokens": self.config.max_output_tokens,
                **self.config.extra_parameters,
            }
            if self.config.temperature is not None:
                parameters["temperature"] = self.config.temperature
            if self.config.reasoning_effort is not None:
                parameters["output_config"] = {
                    "effort": self.config.reasoning_effort
                }
            try:
                response = self.client.messages.create(**parameters)
            except Exception as exc:
                raise ProviderFailure(f"Anthropic Messages request failed: {exc}") from exc
            blocks = [_dump_block(block) for block in (_field(response, "content", []) or [])]
            calls = [block for block in blocks if block.get("type") == "tool_use"]
            messages.append({"role": "assistant", "content": blocks})
            if not calls:
                return ProviderRun("no_final_decision", turn)
            tool_results = []
            for call in calls:
                call_id = call.get("id")
                if not isinstance(call_id, str):
                    raise ProviderFailure("Anthropic tool use has no id")
                result = _execute(session, call.get("name"), call.get("input", {}))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call_id,
                        "content": json.dumps(result, separators=(",", ":")),
                    }
                )
                if session.final_decision is not None:
                    return ProviderRun("submitted", turn)
            messages.append({"role": "user", "content": tool_results})
        return ProviderRun("max_turns", max_turns)


def build_transport(config: ModelConfig, timeout: float) -> Transport:
    if timeout <= 0:
        raise ModelConfigurationError("timeout must be positive")
    if config.transport == "openai_responses":
        return OpenAIResponsesTransport(config, timeout)
    if config.transport == "openai_chat_completions":
        return OpenAIChatCompletionsTransport(config, timeout)
    if config.transport == "anthropic_messages":
        return AnthropicMessagesTransport(config, timeout)
    raise ModelConfigurationError(f"unsupported transport: {config.transport!r}")


__all__ = (
    "ModelConfig",
    "ModelConfigurationError",
    "ProviderFailure",
    "ProviderRun",
    "TRANSPORTS",
    "Transport",
    "build_transport",
    "load_model_config",
)
