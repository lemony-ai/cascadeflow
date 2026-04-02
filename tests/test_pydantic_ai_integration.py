"""Comprehensive tests for the cascadeflow PydanticAI integration.

Tests cover: helpers, full cascade flow, domain policies, tool risk,
cost tracking, harness integration, streaming, fail-open, fail-closed,
CostMetadata, enable_cost_tracking, factory, and availability.

No pydantic-ai package required — all PydanticAI types are faked.
"""

import pytest

from cascadeflow.harness import init, reset, run
from cascadeflow.integrations.pydantic_ai import (
    PYDANTIC_AI_AVAILABLE,
    CascadeFlowModel,
    CascadeFlowPydanticAIConfig,
    CascadeResult,
    CostMetadata,
    DomainPolicy,
    create_cascade_model,
    is_pydantic_ai_available,
)
from cascadeflow.integrations.pydantic_ai.model import (
    _build_cost_metadata,
    _calculate_savings,
    _extract_query_text,
    _extract_text_from_parts,
    _extract_tool_calls_from_parts,
    _extract_usage,
    _normalize_model_name,
)
from cascadeflow.schema.exceptions import BudgetExceededError


# ── Setup / Teardown ─────────────────────────────────────────────────


def setup_function() -> None:
    reset()


# ── Fake PydanticAI types ────────────────────────────────────────────


class FakeUsage:
    """Mimics PydanticAI's RequestUsage with input_tokens/output_tokens."""

    def __init__(self, input_tokens: int = 0, output_tokens: int = 0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeTextPart:
    def __init__(self, content: str):
        self.content = content


class FakeToolCallPart:
    def __init__(self, tool_name: str, description: str = ""):
        self.tool_name = tool_name
        self.description = description


class FakeModelResponse:
    def __init__(self, parts=None, usage=None, model_name="fake-model"):
        self.parts = parts or []
        self.usage = usage or FakeUsage()
        self.model_name = model_name


class FakeUserMessage:
    """Mimics a PydanticAI ModelRequest with parts."""

    def __init__(self, text: str):
        self.parts = [FakeTextPart(text)]


class FakeContentMessage:
    """Message with .content instead of .parts (fallback path)."""

    def __init__(self, text: str):
        self.content = text


class FakeStreamedResponse:
    """Async context manager + async iterator for stream testing."""

    def __init__(self, final_response: FakeModelResponse):
        self._response = final_response
        self._yielded = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._yielded:
            raise StopAsyncIteration
        self._yielded = True
        text = _extract_text_from_parts(self._response.parts)
        return text


class FakeStreamedResponseWithUsage(FakeStreamedResponse):
    """Stream that also exposes usage on the final chunk."""

    def __init__(self, final_response: FakeModelResponse):
        super().__init__(final_response)

    async def __anext__(self):
        if self._yielded:
            raise StopAsyncIteration
        self._yielded = True

        class _Chunk:
            def __init__(self, text, usage):
                self.content = text
                self.usage = usage

        text = _extract_text_from_parts(self._response.parts)
        return _Chunk(text, self._response.usage)


class FakeDrafterModel:
    """Fake PydanticAI Model standing in for the drafter."""

    def __init__(self, response: FakeModelResponse):
        self._response = response
        self.model_name = response.model_name
        self.request_count = 0

    async def request(self, messages=None, model_settings=None, model_request_parameters=None):
        self.request_count += 1
        return self._response

    def request_stream(self, messages=None, model_settings=None, model_request_parameters=None):
        return FakeStreamedResponse(self._response)


class FakeVerifierModel:
    """Fake PydanticAI Model standing in for the verifier."""

    def __init__(self, response: FakeModelResponse):
        self._response = response
        self.model_name = response.model_name
        self.request_count = 0

    async def request(self, messages=None, model_settings=None, model_request_parameters=None):
        self.request_count += 1
        return self._response

    def request_stream(self, messages=None, model_settings=None, model_request_parameters=None):
        return FakeStreamedResponseWithUsage(self._response)


# ── Test data factories ──────────────────────────────────────────────


def _make_messages(text: str = "What is quantum computing?") -> list:
    return [FakeUserMessage(text)]


def _high_quality_response(model_name: str = "gpt-4o-mini") -> FakeModelResponse:
    """A long, well-structured response that passes quality gating."""
    return FakeModelResponse(
        parts=[
            FakeTextPart(
                "Quantum computing is a type of computation that harnesses quantum "
                "mechanical phenomena such as superposition and entanglement. Unlike "
                "classical computers that use bits, quantum computers use qubits that "
                "can exist in multiple states simultaneously, enabling exponential "
                "speedups for certain types of problems."
            )
        ],
        usage=FakeUsage(input_tokens=200, output_tokens=100),
        model_name=model_name,
    )


def _low_quality_response(model_name: str = "gpt-4o-mini") -> FakeModelResponse:
    """A short, vague response that fails quality gating."""
    return FakeModelResponse(
        parts=[FakeTextPart("idk")],
        usage=FakeUsage(input_tokens=200, output_tokens=5),
        model_name=model_name,
    )


def _tool_call_response(
    tool_name: str = "search", model_name: str = "gpt-4o-mini"
) -> FakeModelResponse:
    return FakeModelResponse(
        parts=[FakeToolCallPart(tool_name=tool_name)],
        usage=FakeUsage(input_tokens=150, output_tokens=30),
        model_name=model_name,
    )


# ═══════════════════════════════════════════════════════════════════════
# Helper tests
# ═══════════════════════════════════════════════════════════════════════


def test_extract_text_from_response():
    parts = [FakeTextPart("Hello"), FakeTextPart(" world")]
    assert _extract_text_from_parts(parts) == "Hello world"


def test_extract_text_empty():
    assert _extract_text_from_parts([]) == ""
    assert _extract_text_from_parts(None) == ""


def test_extract_tool_calls():
    parts = [FakeToolCallPart("search"), FakeToolCallPart("delete_all")]
    calls = _extract_tool_calls_from_parts(parts)
    assert len(calls) == 2
    assert calls[0]["name"] == "search"
    assert calls[1]["name"] == "delete_all"


def test_extract_tool_calls_empty():
    assert _extract_tool_calls_from_parts([]) == []


def test_extract_usage():
    resp = FakeModelResponse(usage=FakeUsage(input_tokens=100, output_tokens=50))
    inp, out = _extract_usage(resp)
    assert inp == 100
    assert out == 50


def test_extract_usage_none():
    class NoUsage:
        usage = None

    inp, out = _extract_usage(NoUsage())
    assert inp == 0
    assert out == 0


def test_extract_usage_deprecated_field_names():
    """Backward compat: request_tokens/response_tokens still work."""

    class OldUsage:
        def __init__(self):
            self.request_tokens = 80
            self.response_tokens = 40

    class OldResponse:
        def __init__(self):
            self.usage = OldUsage()

    inp, out = _extract_usage(OldResponse())
    assert inp == 80
    assert out == 40


def test_normalize_model_name_colon():
    assert _normalize_model_name("openai:gpt-4o") == "gpt-4o"


def test_normalize_model_name_slash():
    assert _normalize_model_name("anthropic/claude-haiku-3.5") == "claude-haiku-3.5"


def test_normalize_model_name_plain():
    assert _normalize_model_name("gpt-4o-mini") == "gpt-4o-mini"


def test_extract_query_text_from_parts():
    messages = [FakeUserMessage("Hello world")]
    assert _extract_query_text(messages) == "Hello world"


def test_extract_query_text_from_content():
    messages = [FakeContentMessage("Fallback content")]
    assert _extract_query_text(messages) == "Fallback content"


def test_extract_query_text_empty():
    assert _extract_query_text([]) == ""


def test_extract_query_text_multi_message():
    """Should use the last message only."""
    messages = [FakeUserMessage("First"), FakeUserMessage("Second")]
    assert _extract_query_text(messages) == "Second"


def test_calculate_savings():
    assert _calculate_savings(1.0, 10.0) == 90.0
    assert _calculate_savings(5.0, 10.0) == 50.0
    assert _calculate_savings(0.0, 0.0) == 0.0


def test_build_cost_metadata():
    meta = _build_cost_metadata(
        drafter_input=100,
        drafter_output=50,
        drafter_cost=0.01,
        verifier_input=200,
        verifier_output=100,
        verifier_cost=0.05,
        accepted=False,
        drafter_quality=0.4,
        model_used="verifier",
    )
    assert meta["drafter_tokens"]["input"] == 100
    assert meta["drafter_tokens"]["output"] == 50
    assert meta["verifier_tokens"]["input"] == 200
    assert meta["total_cost"] == pytest.approx(0.06)
    assert meta["model_used"] == "verifier"
    assert meta["accepted"] is False


def test_build_cost_metadata_no_verifier():
    meta = _build_cost_metadata(
        drafter_input=100,
        drafter_output=50,
        drafter_cost=0.01,
        verifier_input=0,
        verifier_output=0,
        verifier_cost=0.0,
        accepted=True,
        drafter_quality=0.8,
        model_used="drafter",
    )
    assert "verifier_tokens" not in meta
    assert meta["total_cost"] == 0.01


# ═══════════════════════════════════════════════════════════════════════
# Full cascade flow
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_drafter_accepted_when_quality_high():
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(quality_threshold=0.5, enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)

    result = await model.request(messages=_make_messages())
    assert result is drafter._response
    assert drafter.request_count == 1
    assert verifier.request_count == 0

    cascade = model.get_last_cascade_result()
    assert cascade is not None
    assert cascade["model_used"] == "drafter"
    assert cascade["accepted"] is True

    cost_meta = model.get_last_cost_metadata()
    assert cost_meta is not None
    assert cost_meta["model_used"] == "drafter"
    assert cost_meta["accepted"] is True


@pytest.mark.asyncio
async def test_escalates_to_verifier_when_quality_low():
    drafter = FakeDrafterModel(_low_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(quality_threshold=0.7, enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)

    result = await model.request(messages=_make_messages())
    assert result is verifier._response
    assert drafter.request_count == 1
    assert verifier.request_count == 1

    cascade = model.get_last_cascade_result()
    assert cascade["model_used"] == "verifier"
    assert cascade["accepted"] is False

    cost_meta = model.get_last_cost_metadata()
    assert cost_meta["model_used"] == "verifier"
    assert cost_meta["accepted"] is False


@pytest.mark.asyncio
async def test_hard_query_skips_drafter():
    """PreRouter routes HARD/EXPERT queries directly to verifier."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.5,
        enable_pre_router=True,
        cascade_complexities=["trivial", "simple"],
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    hard_query = (
        "Analyze the epistemological implications of Godel's incompleteness "
        "theorems on the foundations of mathematics and their relationship to "
        "computational complexity theory, including P vs NP, and how this "
        "intersects with the philosophy of mind, consciousness, and artificial "
        "general intelligence research paradigms."
    )
    messages = _make_messages(hard_query)
    result = await model.request(messages=messages)

    cascade = model.get_last_cascade_result()
    assert cascade is not None
    # PreRouter should classify this as hard/expert and skip drafter
    assert verifier.request_count == 1
    assert cascade["model_used"] == "verifier"
    assert drafter.request_count == 0


@pytest.mark.asyncio
async def test_trivial_query_uses_cascade():
    """PreRouter allows cascade for trivial queries."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(quality_threshold=0.5, enable_pre_router=True)
    model = CascadeFlowModel(drafter, verifier, config=config)

    messages = _make_messages("Hello, how are you?")
    await model.request(messages=messages)

    cascade = model.get_last_cascade_result()
    assert cascade is not None
    assert cascade["model_used"] == "drafter"
    assert cascade["accepted"] is True


# ═══════════════════════════════════════════════════════════════════════
# Domain policies
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_domain_direct_to_verifier():
    """direct_to_verifier policy skips drafter entirely."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.5,
        enable_pre_router=False,
        domain_policies={
            "medical": {"direct_to_verifier": True},
        },
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    messages = _make_messages("What are the medical side effects of aspirin?")
    await model.request(messages=messages)

    assert drafter.request_count == 0
    assert verifier.request_count == 1

    cascade = model.get_last_cascade_result()
    assert cascade["model_used"] == "verifier"
    assert cascade["domain"] == "medical"


@pytest.mark.asyncio
async def test_domain_quality_threshold_override():
    """Per-domain quality threshold override."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.5,
        enable_pre_router=False,
        domain_policies={
            "legal": {"quality_threshold": 0.99},
        },
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    messages = _make_messages("What are the legal implications of this contract?")
    await model.request(messages=messages)

    cascade = model.get_last_cascade_result()
    assert cascade is not None
    assert cascade["model_used"] == "verifier"
    assert cascade["domain"] == "legal"


@pytest.mark.asyncio
async def test_domain_force_verifier():
    """force_verifier runs drafter but always escalates."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.1,
        enable_pre_router=False,
        domain_policies={
            "finance": {"force_verifier": True},
        },
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    messages = _make_messages("Show me the finance quarterly report analysis.")
    await model.request(messages=messages)

    assert drafter.request_count == 1
    assert verifier.request_count == 1

    cascade = model.get_last_cascade_result()
    assert cascade["model_used"] == "verifier"
    assert cascade["accepted"] is False


@pytest.mark.asyncio
async def test_domain_no_match_uses_default_threshold():
    """No domain match -> default quality threshold."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3,
        enable_pre_router=False,
        domain_policies={
            "medical": {"quality_threshold": 0.99},
        },
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    # This query does NOT contain "medical"
    messages = _make_messages("Tell me about quantum computing.")
    await model.request(messages=messages)

    cascade = model.get_last_cascade_result()
    assert cascade["model_used"] == "drafter"
    assert cascade["domain"] is None


# ═══════════════════════════════════════════════════════════════════════
# Tool risk
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_high_risk_tool_escalates():
    """High-risk tool calls force escalation to verifier."""
    drafter_resp = FakeModelResponse(
        parts=[FakeToolCallPart("delete_all_users")],
        usage=FakeUsage(input_tokens=100, output_tokens=20),
        model_name="gpt-4o-mini",
    )
    drafter = FakeDrafterModel(drafter_resp)
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.1,
        enable_pre_router=False,
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    messages = _make_messages("Delete all the users from the database.")
    await model.request(messages=messages)

    cascade = model.get_last_cascade_result()
    assert cascade is not None
    assert cascade["model_used"] == "verifier"


@pytest.mark.asyncio
async def test_low_risk_tool_accepted():
    """Low-risk tool calls stay on drafter when quality is good."""
    drafter_resp = FakeModelResponse(
        parts=[
            FakeTextPart(
                "I'll search for that information for you. Let me look it up "
                "in our knowledge base to find the most relevant results."
            ),
            FakeToolCallPart("search"),
        ],
        usage=FakeUsage(input_tokens=100, output_tokens=30),
        model_name="gpt-4o-mini",
    )
    drafter = FakeDrafterModel(drafter_resp)
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(quality_threshold=0.3, enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)

    messages = _make_messages("Search for recent news about AI.")
    await model.request(messages=messages)

    cascade = model.get_last_cascade_result()
    assert cascade is not None
    assert cascade["model_used"] == "drafter"
    assert verifier.request_count == 0


# ═══════════════════════════════════════════════════════════════════════
# Cost tracking
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_cost_metadata_on_drafter_accepted():
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(quality_threshold=0.3, enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)

    await model.request(messages=_make_messages())

    cascade = model.get_last_cascade_result()
    assert cascade["drafter_cost"] > 0
    assert cascade["verifier_cost"] == 0.0
    assert cascade["total_cost"] == cascade["drafter_cost"]
    assert cascade["savings_percentage"] > 0


@pytest.mark.asyncio
async def test_cost_metadata_on_verifier_used():
    drafter = FakeDrafterModel(_low_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(quality_threshold=0.7, enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)

    await model.request(messages=_make_messages())

    cascade = model.get_last_cascade_result()
    assert cascade["drafter_cost"] > 0
    assert cascade["verifier_cost"] > 0
    assert cascade["total_cost"] == cascade["drafter_cost"] + cascade["verifier_cost"]
    assert cascade["savings_percentage"] == 0.0


@pytest.mark.asyncio
async def test_cascade_result_stored():
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(quality_threshold=0.3, enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)

    assert model.get_last_cascade_result() is None
    assert model.get_last_cost_metadata() is None

    await model.request(messages=_make_messages())

    cascade = model.get_last_cascade_result()
    assert cascade is not None
    assert "content" in cascade
    assert "model_used" in cascade
    assert "drafter_quality" in cascade
    assert "latency_ms" in cascade
    assert cascade["latency_ms"] > 0

    cost_meta = model.get_last_cost_metadata()
    assert cost_meta is not None
    assert "drafter_tokens" in cost_meta
    assert "total_cost" in cost_meta


@pytest.mark.asyncio
async def test_enable_cost_tracking_false_skips_harness():
    """When enable_cost_tracking=False, harness metrics are NOT recorded."""
    init(mode="observe", budget=5.0)

    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3,
        enable_pre_router=False,
        enable_cost_tracking=False,
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    with run(budget=5.0) as ctx:
        await model.request(messages=_make_messages())
        # No harness recording should have happened
        assert ctx.step_count == 0
        assert ctx.cost == 0.0


@pytest.mark.asyncio
async def test_cost_metadata_type_populated():
    """Verify CostMetadata is properly populated with token details."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(quality_threshold=0.3, enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)

    await model.request(messages=_make_messages())

    cost_meta = model.get_last_cost_metadata()
    assert cost_meta is not None
    assert cost_meta["drafter_tokens"]["input"] == 200
    assert cost_meta["drafter_tokens"]["output"] == 100
    assert cost_meta["drafter_cost"] > 0
    assert cost_meta["savings_percentage"] > 0
    assert cost_meta["accepted"] is True


# ═══════════════════════════════════════════════════════════════════════
# Harness integration
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_harness_metrics_updated():
    init(mode="observe", budget=5.0)

    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(quality_threshold=0.3, enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)

    with run(budget=5.0) as ctx:
        await model.request(messages=_make_messages())
        assert ctx.step_count >= 1
        assert ctx.cost > 0
        assert ctx.energy_used > 0
        assert ctx.model_used is not None


@pytest.mark.asyncio
async def test_budget_exceeded_raises_error():
    init(mode="enforce", budget=1.0)

    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3, enable_pre_router=False, enable_budget_gate=True
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    with run(budget=1.0) as ctx:
        ctx.budget_remaining = 0.0
        with pytest.raises(BudgetExceededError):
            await model.request(messages=_make_messages())


@pytest.mark.asyncio
async def test_observe_mode_allows_over_budget():
    init(mode="observe", budget=1.0)

    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3, enable_pre_router=False, enable_budget_gate=True
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    with run(budget=1.0) as ctx:
        ctx.budget_remaining = 0.0
        result = await model.request(messages=_make_messages())
        assert result is not None


@pytest.mark.asyncio
async def test_budget_gate_records_stop_trace():
    init(mode="enforce", budget=1.0)

    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3, enable_pre_router=False, enable_budget_gate=True
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    with run(budget=1.0) as ctx:
        ctx.budget_remaining = 0.0
        try:
            await model.request(messages=_make_messages())
        except BudgetExceededError:
            pass
        assert ctx.last_action == "stop"


# ═══════════════════════════════════════════════════════════════════════
# Streaming
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_stream_drafter_accepted():
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3, enable_pre_router=False, enable_budget_gate=False
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    chunks = []
    async with model.request_stream(messages=_make_messages()) as stream:
        async for chunk in stream:
            chunks.append(chunk)

    assert len(chunks) > 0
    assert verifier.request_count == 0

    cascade = model.get_last_cascade_result()
    assert cascade is not None
    assert cascade["model_used"] == "drafter"
    assert cascade["accepted"] is True
    assert cascade["drafter_cost"] > 0


@pytest.mark.asyncio
async def test_stream_escalates_to_verifier():
    """Low-quality drafter -> verifier stream is used instead."""
    drafter = FakeDrafterModel(_low_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.9, enable_pre_router=False, enable_budget_gate=False
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    chunks = []
    async with model.request_stream(messages=_make_messages()) as stream:
        async for chunk in stream:
            chunks.append(chunk)

    cascade = model.get_last_cascade_result()
    assert cascade is not None
    assert cascade["model_used"] == "verifier"
    assert cascade["accepted"] is False
    assert cascade["drafter_cost"] > 0


@pytest.mark.asyncio
async def test_stream_direct_to_verifier_domain():
    """Domain policy direct_to_verifier works in streaming mode."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3,
        enable_pre_router=False,
        enable_budget_gate=False,
        domain_policies={
            "medical": {"direct_to_verifier": True},
        },
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    chunks = []
    async with model.request_stream(
        messages=_make_messages("What are the medical effects?")
    ) as stream:
        async for chunk in stream:
            chunks.append(chunk)

    assert drafter.request_count == 0
    cascade = model.get_last_cascade_result()
    assert cascade["model_used"] == "verifier"


@pytest.mark.asyncio
async def test_stream_budget_gate():
    """Budget gate works in streaming mode."""
    init(mode="enforce", budget=1.0)

    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3,
        enable_pre_router=False,
        enable_budget_gate=True,
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    with run(budget=1.0) as ctx:
        ctx.budget_remaining = 0.0
        with pytest.raises(BudgetExceededError):
            async with model.request_stream(messages=_make_messages()) as stream:
                async for _ in stream:
                    pass


@pytest.mark.asyncio
async def test_stream_cost_tracking():
    """Streaming records harness metrics."""
    init(mode="observe", budget=5.0)

    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3, enable_pre_router=False, enable_budget_gate=False
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    with run(budget=5.0) as ctx:
        async with model.request_stream(messages=_make_messages()) as stream:
            async for _ in stream:
                pass
        assert ctx.step_count >= 1
        assert ctx.cost > 0


# ═══════════════════════════════════════════════════════════════════════
# Fail-open and fail-closed
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fail_open_on_quality_check_error(monkeypatch):
    """Quality error with fail_open=True -> accept drafter."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.5, enable_pre_router=False, fail_open=True
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    import cascadeflow.integrations.pydantic_ai.model as model_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("quality scoring exploded")

    monkeypatch.setattr(model_mod, "score_response", _boom)

    result = await model.request(messages=_make_messages())
    assert result is drafter._response
    assert verifier.request_count == 0


@pytest.mark.asyncio
async def test_fail_closed_on_quality_check_error(monkeypatch):
    """Quality error with fail_open=False -> raises error."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.5, enable_pre_router=False, fail_open=False
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    import cascadeflow.integrations.pydantic_ai.model as model_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("quality scoring exploded")

    monkeypatch.setattr(model_mod, "score_response", _boom)

    with pytest.raises(RuntimeError, match="quality scoring exploded"):
        await model.request(messages=_make_messages())


@pytest.mark.asyncio
async def test_fail_open_on_pre_router_error(monkeypatch):
    """PreRouter error with fail_open=True -> proceed with cascade."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3, enable_pre_router=True, fail_open=True
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    if model._pre_router is not None:

        async def _boom(*args, **kwargs):
            raise RuntimeError("pre-router exploded")

        monkeypatch.setattr(model._pre_router, "route", _boom)

    result = await model.request(messages=_make_messages())
    assert result is drafter._response


@pytest.mark.asyncio
async def test_fail_closed_on_pre_router_error(monkeypatch):
    """PreRouter error with fail_open=False -> raises error."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(
        quality_threshold=0.3, enable_pre_router=True, fail_open=False
    )
    model = CascadeFlowModel(drafter, verifier, config=config)

    if model._pre_router is not None:

        async def _boom(*args, **kwargs):
            raise RuntimeError("pre-router exploded")

        monkeypatch.setattr(model._pre_router, "route", _boom)

        with pytest.raises(RuntimeError, match="pre-router exploded"):
            await model.request(messages=_make_messages())


# ═══════════════════════════════════════════════════════════════════════
# Factory & availability
# ═══════════════════════════════════════════════════════════════════════


def test_create_cascade_model_factory():
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    model = create_cascade_model(
        drafter,
        verifier,
        quality_threshold=0.8,
        enable_pre_router=False,
        fail_open=True,
        enable_cost_tracking=False,
    )

    assert isinstance(model, CascadeFlowModel)
    assert model._config.quality_threshold == 0.8
    assert model._config.fail_open is True
    assert model._config.enable_pre_router is False
    assert model._config.enable_cost_tracking is False


def test_is_pydantic_ai_available():
    result = is_pydantic_ai_available()
    assert isinstance(result, bool)


def test_model_name_property():
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)

    assert "cascadeflow:" in model.model_name
    assert "gpt-4o-mini" in model.model_name
    assert "gpt-4o" in model.model_name


def test_system_property():
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)
    assert model.system == "cascadeflow"


def test_config_defaults():
    config = CascadeFlowPydanticAIConfig()
    assert config.quality_threshold == 0.7
    assert config.enable_pre_router is True
    assert config.cascade_complexities == ["trivial", "simple", "moderate"]
    assert config.domain_policies is None
    assert config.enable_cost_tracking is True
    assert config.fail_open is True
    assert config.enable_budget_gate is True


def test_model_inherits_from_base():
    """CascadeFlowModel should inherit from the Model base class."""
    drafter = FakeDrafterModel(_high_quality_response("gpt-4o-mini"))
    verifier = FakeVerifierModel(_high_quality_response("gpt-4o"))

    config = CascadeFlowPydanticAIConfig(enable_pre_router=False)
    model = CascadeFlowModel(drafter, verifier, config=config)

    # When pydantic-ai is installed, the base is the real Model ABC.
    # When not installed, the base falls back to `object`.
    # Either way, the model should be an instance of the resolved base.
    from cascadeflow.integrations.pydantic_ai.model import _PydanticAIModel

    assert isinstance(model, _PydanticAIModel)

    # When pydantic-ai is installed, also verify against real Model
    try:
        from pydantic_ai.models import Model

        assert isinstance(model, Model)
    except ImportError:
        pass


def test_domain_policy_type():
    """Verify DomainPolicy is a proper TypedDict."""
    policy: DomainPolicy = {
        "quality_threshold": 0.9,
        "force_verifier": True,
    }
    assert policy["quality_threshold"] == 0.9
    assert policy["force_verifier"] is True


# ═══════════════════════════════════════════════════════════════════════
# Production readiness — real PydanticAI types (skip when not installed)
# ═══════════════════════════════════════════════════════════════════════

_REAL_PYDANTIC_AI = False
try:
    from pydantic_ai.models import Model as _RealModel, ModelResponse as _RealModelResponse
    from pydantic_ai.messages import TextPart as _RealTextPart, ModelRequest, UserPromptPart
    from pydantic_ai.usage import RequestUsage as _RealRequestUsage

    _REAL_PYDANTIC_AI = True
except ImportError:
    pass


@pytest.mark.skipif(not _REAL_PYDANTIC_AI, reason="pydantic-ai not installed")
class TestRealPydanticAICompat:
    """Tests that run with the real pydantic-ai package to verify protocol compat."""

    @staticmethod
    def _make_real_drafter(text: str = "High quality draft response about the topic."):
        class _D(_RealModel):
            @property
            def model_name(self):
                return "test-drafter"

            @property
            def system(self):
                return "test"

            async def request(self, messages, model_settings=None, model_request_parameters=None):
                return _RealModelResponse(
                    parts=[_RealTextPart(content=text)],
                    usage=_RealRequestUsage(input_tokens=100, output_tokens=50),
                    model_name=self.model_name,
                )

        return _D()

    @staticmethod
    def _make_real_verifier(text: str = "Verified high quality response about the topic."):
        class _V(_RealModel):
            @property
            def model_name(self):
                return "test-verifier"

            @property
            def system(self):
                return "test"

            async def request(self, messages, model_settings=None, model_request_parameters=None):
                return _RealModelResponse(
                    parts=[_RealTextPart(content=text)],
                    usage=_RealRequestUsage(input_tokens=200, output_tokens=100),
                    model_name=self.model_name,
                )

        return _V()

    def test_is_model_subclass(self):
        assert issubclass(CascadeFlowModel, _RealModel)

    def test_isinstance_check(self):
        model = create_cascade_model(
            self._make_real_drafter(),
            self._make_real_verifier(),
            quality_threshold=0.5,
            enable_pre_router=False,
        )
        assert isinstance(model, _RealModel)

    @pytest.mark.asyncio
    async def test_request_returns_real_model_response(self):
        model = create_cascade_model(
            self._make_real_drafter(),
            self._make_real_verifier(),
            quality_threshold=0.5,
            enable_pre_router=False,
        )
        messages = [ModelRequest(parts=[UserPromptPart(content="Hello")])]
        result = await model.request(
            messages=messages, model_settings=None, model_request_parameters=None
        )
        assert isinstance(result, _RealModelResponse)
        assert result.usage.input_tokens > 0
        assert result.usage.output_tokens > 0

    @pytest.mark.asyncio
    async def test_escalation_with_real_types(self):
        model = create_cascade_model(
            self._make_real_drafter(text="idk"),
            self._make_real_verifier(),
            quality_threshold=0.7,
            enable_pre_router=False,
        )
        messages = [ModelRequest(parts=[UserPromptPart(content="Explain quantum entanglement")])]
        result = await model.request(
            messages=messages, model_settings=None, model_request_parameters=None
        )
        cascade = model.get_last_cascade_result()
        assert cascade["model_used"] == "verifier"
        assert cascade["accepted"] is False

    @pytest.mark.asyncio
    async def test_through_pydantic_ai_agent(self):
        from pydantic_ai import Agent

        model = create_cascade_model(
            self._make_real_drafter(
                text="Quantum computing uses qubits that leverage superposition and "
                "entanglement to process information in fundamentally new ways."
            ),
            self._make_real_verifier(),
            quality_threshold=0.5,
            enable_pre_router=False,
            enable_budget_gate=False,
        )
        agent = Agent(model=model)
        result = await agent.run("What is quantum computing?")
        assert len(result.output) > 0
        cascade = model.get_last_cascade_result()
        assert cascade["model_used"] in ("drafter", "verifier")
        assert cascade["total_cost"] > 0

    @pytest.mark.asyncio
    async def test_harness_integration_with_real_types(self):
        from cascadeflow.harness import init, run, reset

        reset()
        init(mode="observe", budget=10.0)

        model = create_cascade_model(
            self._make_real_drafter(),
            self._make_real_verifier(),
            quality_threshold=0.5,
            enable_pre_router=False,
        )

        with run(budget=10.0) as ctx:
            messages = [ModelRequest(parts=[UserPromptPart(content="Hello")])]
            await model.request(
                messages=messages, model_settings=None, model_request_parameters=None
            )
            assert ctx.step_count >= 1
            assert ctx.cost > 0
            assert ctx.energy_used > 0

        reset()
