from __future__ import annotations

from types import SimpleNamespace

from algoworlds.providers import (
    AnthropicMessagesTransport,
    ModelConfig,
    OpenAIChatCompletionsTransport,
    OpenAIResponsesTransport,
)


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": "Submit.",
            "parameters": {
                "type": "object",
                "properties": {"answer": {"type": "integer"}},
                "required": ["answer"],
            },
        },
    }
]


class Session:
    tool_schemas = SCHEMAS

    def __init__(self) -> None:
        self.final_decision = None

    def call(self, name, args):
        assert name == "submit_answer"
        self.final_decision = args
        return {"accepted": True}


class Create:
    def __init__(self, response) -> None:
        self.response = response
        self.parameters = None

    def create(self, **parameters):
        self.parameters = parameters
        return self.response


class SequenceCreate:
    def __init__(self, responses) -> None:
        self.responses = iter(responses)
        self.parameters = []

    def create(self, **parameters):
        self.parameters.append(parameters)
        return next(self.responses)


def _config(transport: str) -> ModelConfig:
    return ModelConfig(
        label="model",
        transport=transport,
        model="model-id",
        api_key_env="MODEL_API_KEY",
    )


def test_responses_transport_executes_native_function_call() -> None:
    create = Create(
        {
            "id": "response-1",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "submit_answer",
                    "arguments": '{"answer":7}',
                }
            ],
        }
    )
    transport = object.__new__(OpenAIResponsesTransport)
    transport.config = _config("openai_responses")
    transport.client = SimpleNamespace(responses=create)
    session = Session()
    result = transport.run(session, "system", "request", max_turns=2)
    assert result.termination == "submitted"
    assert session.final_decision == {"answer": 7}
    assert create.parameters["tools"][0]["name"] == "submit_answer"


def test_responses_transport_repeats_instructions_across_turns() -> None:
    create = SequenceCreate(
        [
            {
                "id": "response-1",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "inspect",
                        "arguments": "{}",
                    }
                ],
            },
            {"id": "response-2", "output": []},
        ]
    )
    transport = object.__new__(OpenAIResponsesTransport)
    transport.config = _config("openai_responses")
    transport.client = SimpleNamespace(responses=create)
    session = Session()
    session.call = lambda name, args: {"observed": True}

    result = transport.run(session, "system", "request", max_turns=2)

    assert result.termination == "no_final_decision"
    assert [parameters["instructions"] for parameters in create.parameters] == [
        "system",
        "system",
    ]
    assert create.parameters[1]["previous_response_id"] == "response-1"


def test_chat_completions_transport_executes_native_tool_call() -> None:
    create = Create(
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {
                                    "name": "submit_answer",
                                    "arguments": '{"answer":7}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
    )
    transport = object.__new__(OpenAIChatCompletionsTransport)
    transport.config = _config("openai_chat_completions")
    transport.client = SimpleNamespace(
        chat=SimpleNamespace(completions=create)
    )
    session = Session()
    result = transport.run(session, "system", "request", max_turns=2)
    assert result.termination == "submitted"
    assert session.final_decision == {"answer": 7}
    assert create.parameters["tools"] == SCHEMAS


def test_anthropic_transport_executes_native_tool_use() -> None:
    create = Create(
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call-1",
                    "name": "submit_answer",
                    "input": {"answer": 7},
                }
            ]
        }
    )
    transport = object.__new__(AnthropicMessagesTransport)
    transport.config = _config("anthropic_messages")
    transport.client = SimpleNamespace(messages=create)
    session = Session()
    result = transport.run(session, "system", "request", max_turns=2)
    assert result.termination == "submitted"
    assert session.final_decision == {"answer": 7}
    assert create.parameters["tools"][0]["name"] == "submit_answer"
