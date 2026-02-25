import pytest

from cascadeflow.harness import init, reset, run
import cascadeflow.integrations.openai_agents as openai_agents_integration
from cascadeflow.integrations.openai_agents import (
    CascadeFlowModelProvider,
    OpenAIAgentsIntegrationConfig,
)


def setup_function() -> None:
    reset()


def test_requires_sdk_for_default_provider(monkeypatch):
    monkeypatch.setattr(openai_agents_integration, "OPENAI_AGENTS_SDK_AVAILABLE", False)
    with pytest.raises(ImportError):
        CascadeFlowModelProvider()


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeResponse:
    def __init__(self, input_tokens: int = 0, output_tokens: int = 0, output=None) -> None:
        self.usage = _FakeUsage(input_tokens=input_tokens, output_tokens=output_tokens)
        self.output = output or []


class _FakeEvent:
    def __init__(self, response=None) -> None:
        self.response = response


class _FakeAsyncStream:
    def __init__(self, events) -> None:
        self._events = list(events)
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._events):
            raise StopAsyncIteration
        event = self._events[self._index]
        self._index += 1
        return event


class _FakeModel:
    def __init__(self, response: _FakeResponse, stream_events=None) -> None:
        self._response = response
        self._stream_events = stream_events or []
        self.last_kwargs = None

    async def get_response(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response

    def stream_response(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeAsyncStream(self._stream_events)


class _FakeBaseProvider:
    def __init__(self, model: _FakeModel) -> None:
        self._model = model
        self.requested_models = []

    def get_model(self, model_name):
        self.requested_models.append(model_name)
        return self._model


def _response_call_kwargs():
    return {
        "system_instructions": None,
        "input_data": "hello",
        "model_settings": None,
        "tools": [],
        "output_schema": None,
        "handoffs": [],
        "tracing": None,
        "previous_response_id": None,
        "conversation_id": None,
        "prompt": None,
    }


@pytest.mark.asyncio
async def test_metrics_updated_from_get_response():
    init(mode="observe", budget=2.0)

    output = [{"type": "function_call", "name": "lookup"}]
    response = _FakeResponse(input_tokens=200, output_tokens=100, output=output)
    model = _FakeModel(response=response)
    provider = CascadeFlowModelProvider(base_provider=_FakeBaseProvider(model))

    wrapped = provider.get_model("gpt-4o")

    with run(budget=2.0) as ctx:
        await wrapped.get_response(**_response_call_kwargs())
        assert ctx.step_count == 1
        assert ctx.tool_calls == 1
        assert ctx.cost > 0
        assert ctx.energy_used > 0
        assert ctx.budget_remaining is not None
        assert ctx.budget_remaining < 2.0
        assert ctx.model_used == "gpt-4o"


@pytest.mark.asyncio
async def test_tool_gating_enforced_when_limit_reached():
    init(mode="enforce", max_tool_calls=0, budget=1.0)

    response = _FakeResponse(input_tokens=10, output_tokens=5)
    model = _FakeModel(response=response)
    provider = CascadeFlowModelProvider(base_provider=_FakeBaseProvider(model))
    wrapped = provider.get_model("gpt-4o-mini")

    kwargs = _response_call_kwargs()
    kwargs["tools"] = [{"name": "lookup"}]

    with run(max_tool_calls=0, budget=1.0) as ctx:
        await wrapped.get_response(**kwargs)
        assert model.last_kwargs is not None
        assert model.last_kwargs["tools"] == []
        assert ctx.last_action == "deny_tool"


def test_switches_to_cheapest_candidate_under_budget_pressure():
    init(mode="enforce", budget=1.0)

    response = _FakeResponse()
    model = _FakeModel(response=response)
    base_provider = _FakeBaseProvider(model)
    config = OpenAIAgentsIntegrationConfig(model_candidates=["gpt-4o", "gpt-4o-mini"])
    provider = CascadeFlowModelProvider(base_provider=base_provider, config=config)

    with run(budget=1.0) as ctx:
        ctx.cost = 0.9
        ctx.budget_remaining = 0.1
        provider.get_model("gpt-4o")
        assert base_provider.requested_models[-1] == "gpt-4o-mini"
        assert ctx.last_action == "switch_model"


@pytest.mark.asyncio
async def test_stream_response_updates_metrics():
    init(mode="observe", budget=3.0)

    final_response = _FakeResponse(
        input_tokens=120,
        output_tokens=60,
        output=[{"type": "function_call", "name": "tool_a"}],
    )
    stream_events = [_FakeEvent(response=final_response)]
    model = _FakeModel(response=final_response, stream_events=stream_events)
    provider = CascadeFlowModelProvider(base_provider=_FakeBaseProvider(model))
    wrapped = provider.get_model("gpt-4o-mini")

    with run(budget=3.0) as ctx:
        async for _ in wrapped.stream_response(
            **_response_call_kwargs(),
            text_format=None,
        ):
            pass

        assert ctx.step_count == 1
        assert ctx.tool_calls == 1
        assert ctx.cost > 0
        assert ctx.model_used == "gpt-4o-mini"
