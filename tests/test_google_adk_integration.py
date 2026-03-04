"""Tests for cascadeflow.integrations.google_adk harness integration.

google-adk is not installed in test environments, so we use fake ADK types
and test the integration logic directly against HarnessRunContext.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from cascadeflow.harness import init, reset, run

# Import the module directly — it does not require google-adk at import time
# (GOOGLE_ADK_AVAILABLE will be False, but all functions/classes are still defined).
import cascadeflow.integrations.google_adk as adk_mod


# ---------------------------------------------------------------------------
# Fake ADK types
# ---------------------------------------------------------------------------


class FakeUsageMetadata:
    """Stand-in for google.genai.types.GenerateContentResponseUsageMetadata."""

    def __init__(
        self,
        prompt_token_count: int = 0,
        candidates_token_count: int = 0,
    ):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count


class FakePart:
    """Stand-in for google.genai.types.Part."""

    def __init__(self, *, text: str | None = None, function_call: object | None = None):
        self.text = text
        self.function_call = function_call


class FakeContent:
    """Stand-in for google.genai.types.Content."""

    def __init__(self, parts: list | None = None):
        self.parts = parts or []


class FakeLlmResponse:
    """Stand-in for google.adk.models.LlmResponse."""

    def __init__(
        self,
        *,
        content: FakeContent | None = None,
        usage_metadata: FakeUsageMetadata | None = None,
    ):
        self.content = content
        self.usage_metadata = usage_metadata


class FakeLlmRequest:
    """Stand-in for google.adk.models.LlmRequest."""

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model


class FakeCallbackContext:
    """Stand-in for google.adk.agents.CallbackContext."""

    def __init__(
        self,
        invocation_id: str = "inv-001",
        agent_name: str = "test-agent",
    ):
        self.invocation_id = invocation_id
        self.agent_name = agent_name


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_adk_state():
    """Reset harness and ADK module state before every test."""
    reset()
    adk_mod._config = adk_mod.GoogleADKHarnessConfig()
    adk_mod._plugin_instance = None
    adk_mod._enabled = False


# ---------------------------------------------------------------------------
# _normalize_model_name
# ---------------------------------------------------------------------------


class TestNormalizeModelName:
    def test_plain_model(self):
        assert adk_mod._normalize_model_name("gemini-2.5-flash") == "gemini-2.5-flash"

    def test_strips_provider_prefix(self):
        assert adk_mod._normalize_model_name("openai/gpt-4o") == "gpt-4o"

    def test_strips_models_prefix(self):
        assert adk_mod._normalize_model_name("models/gemini-2.5-flash") == "gemini-2.5-flash"

    def test_strips_litellm_prefix(self):
        assert adk_mod._normalize_model_name("vertex_ai/gemini-2.5-pro") == "gemini-2.5-pro"

    def test_no_slash_passthrough(self):
        assert adk_mod._normalize_model_name("gpt-4o-mini") == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# _count_function_calls
# ---------------------------------------------------------------------------


class TestCountFunctionCalls:
    def test_no_content(self):
        assert adk_mod._count_function_calls(None) == 0

    def test_no_parts(self):
        content = FakeContent(parts=[])
        assert adk_mod._count_function_calls(content) == 0

    def test_text_only(self):
        content = FakeContent(parts=[FakePart(text="hello")])
        assert adk_mod._count_function_calls(content) == 0

    def test_counts_function_calls(self):
        content = FakeContent(
            parts=[
                FakePart(text="thinking..."),
                FakePart(function_call={"name": "search", "args": {}}),
                FakePart(function_call={"name": "calculate", "args": {}}),
            ]
        )
        assert adk_mod._count_function_calls(content) == 2


# ---------------------------------------------------------------------------
# Cost / energy estimation (via shared pricing)
# ---------------------------------------------------------------------------


class TestEstimation:
    def test_estimate_cost_known_model(self):
        from cascadeflow.harness.pricing import estimate_cost

        cost = estimate_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.15 + 0.60)

    def test_estimate_cost_unknown_model_uses_default(self):
        from cascadeflow.harness.pricing import estimate_cost

        cost = estimate_cost("unknown-model", 1_000_000, 0)
        assert cost == pytest.approx(2.50)

    def test_estimate_energy_known_model(self):
        from cascadeflow.harness.pricing import estimate_energy

        energy = estimate_energy("gemini-2.5-flash", 100, 100)
        # coeff=0.3, output_weight=1.5
        assert energy == pytest.approx(0.3 * (100 + 100 * 1.5))

    def test_estimate_energy_unknown_model(self):
        from cascadeflow.harness.pricing import estimate_energy

        energy = estimate_energy("unknown-model", 100, 100)
        # default coeff=1.0
        assert energy == pytest.approx(1.0 * (100 + 100 * 1.5))


# ---------------------------------------------------------------------------
# before_model_callback
# ---------------------------------------------------------------------------


class TestBeforeModelCallback:
    @pytest.fixture
    def plugin(self):
        return adk_mod.CascadeFlowADKPlugin()

    async def test_no_run_context_returns_none(self, plugin):
        ctx = FakeCallbackContext()
        req = FakeLlmRequest()
        result = await plugin.before_model_callback(ctx, req)
        assert result is None

    async def test_observe_mode_allows_over_budget(self, plugin):
        init(mode="observe", budget=0.001)
        with run(budget=0.001) as run_ctx:
            run_ctx.cost = 0.002
            result = await plugin.before_model_callback(
                FakeCallbackContext(), FakeLlmRequest()
            )
            assert result is None  # observe never blocks

    async def test_enforce_blocks_when_budget_exhausted(self, plugin):
        init(mode="enforce", budget=0.001)
        with run(budget=0.001) as run_ctx:
            run_ctx.cost = 0.001
            result = await plugin.before_model_callback(
                FakeCallbackContext(), FakeLlmRequest("gemini-2.5-flash")
            )
            assert result is not None  # short-circuit response
            assert run_ctx.last_action == "stop"
            trace = run_ctx.trace()
            assert trace[-1]["reason"] == "budget_exhausted"

    async def test_enforce_blocked_call_does_not_leak_state(self, plugin):
        init(mode="enforce", budget=0.001)
        with run(budget=0.001) as run_ctx:
            run_ctx.cost = 0.001
            cb_ctx = FakeCallbackContext()
            await plugin.before_model_callback(cb_ctx, FakeLlmRequest())
            key = plugin._callback_key(cb_ctx)
            assert key not in plugin._call_start_times
            assert key not in plugin._call_models

    async def test_enforce_allows_under_budget(self, plugin):
        init(mode="enforce", budget=1.0)
        with run(budget=1.0) as run_ctx:
            run_ctx.cost = 0.5
            result = await plugin.before_model_callback(
                FakeCallbackContext(), FakeLlmRequest()
            )
            assert result is None

    async def test_records_start_time_and_model(self, plugin):
        init(mode="observe")
        with run():
            cb_ctx = FakeCallbackContext()
            await plugin.before_model_callback(cb_ctx, FakeLlmRequest("gpt-4o"))
            key = plugin._callback_key(cb_ctx)
            assert key in plugin._call_start_times
            assert plugin._call_models[key] == "gpt-4o"

    async def test_normalizes_model_name(self, plugin):
        init(mode="observe")
        with run():
            cb_ctx = FakeCallbackContext()
            await plugin.before_model_callback(cb_ctx, FakeLlmRequest("openai/gpt-4o"))
            key = plugin._callback_key(cb_ctx)
            assert plugin._call_models[key] == "gpt-4o"

    async def test_budget_gate_disabled_in_config(self):
        plugin = adk_mod.CascadeFlowADKPlugin(
            config=adk_mod.GoogleADKHarnessConfig(enable_budget_gate=False)
        )
        init(mode="enforce", budget=0.001)
        with run(budget=0.001) as run_ctx:
            run_ctx.cost = 0.002
            result = await plugin.before_model_callback(
                FakeCallbackContext(), FakeLlmRequest()
            )
            assert result is None  # gate disabled

    async def test_fail_open_swallows_errors(self, plugin):
        init(mode="enforce")
        with run():
            with patch(
                "cascadeflow.integrations.google_adk.get_current_run",
                side_effect=RuntimeError("boom"),
            ):
                result = await plugin.before_model_callback(
                    FakeCallbackContext(), FakeLlmRequest()
                )
                assert result is None


# ---------------------------------------------------------------------------
# after_model_callback
# ---------------------------------------------------------------------------


class TestAfterModelCallback:
    @pytest.fixture
    def plugin(self):
        return adk_mod.CascadeFlowADKPlugin()

    async def test_no_run_context_returns_none(self, plugin):
        result = await plugin.after_model_callback(
            FakeCallbackContext(),
            FakeLlmResponse(),
        )
        assert result is None

    async def test_updates_run_metrics_with_usage_metadata(self, plugin):
        init(mode="observe")
        with run(budget=1.0) as run_ctx:
            cb_ctx = FakeCallbackContext()
            key = plugin._callback_key(cb_ctx)
            plugin._call_start_times[key] = time.monotonic() - 0.1
            plugin._call_models[key] = "gemini-2.5-flash"

            response = FakeLlmResponse(
                usage_metadata=FakeUsageMetadata(
                    prompt_token_count=100,
                    candidates_token_count=50,
                ),
                content=FakeContent(parts=[FakePart(text="done")]),
            )
            await plugin.after_model_callback(cb_ctx, response)

            assert run_ctx.step_count == 1
            assert run_ctx.cost > 0
            assert run_ctx.energy_used > 0
            assert run_ctx.latency_used_ms > 0
            assert run_ctx.model_used == "gemini-2.5-flash"
            assert run_ctx.last_action == "allow"

    async def test_fallback_token_estimation(self, plugin):
        """When usage_metadata is missing, estimate from content text."""
        init(mode="observe")
        with run() as run_ctx:
            cb_ctx = FakeCallbackContext()
            key = plugin._callback_key(cb_ctx)
            plugin._call_models[key] = "gemini-2.5-flash"

            response = FakeLlmResponse(
                content=FakeContent(parts=[FakePart(text="x" * 400)]),
            )
            await plugin.after_model_callback(cb_ctx, response)

            assert run_ctx.cost > 0
            assert run_ctx.step_count == 1

    async def test_counts_tool_calls(self, plugin):
        init(mode="observe")
        with run() as run_ctx:
            cb_ctx = FakeCallbackContext()
            key = plugin._callback_key(cb_ctx)
            plugin._call_models[key] = "gemini-2.5-flash"

            response = FakeLlmResponse(
                usage_metadata=FakeUsageMetadata(100, 50),
                content=FakeContent(
                    parts=[
                        FakePart(function_call={"name": "search"}),
                        FakePart(function_call={"name": "calc"}),
                    ]
                ),
            )
            await plugin.after_model_callback(cb_ctx, response)
            assert run_ctx.tool_calls == 2

    async def test_updates_budget_remaining(self, plugin):
        init(mode="enforce", budget=1.0)
        with run(budget=1.0) as run_ctx:
            cb_ctx = FakeCallbackContext()
            key = plugin._callback_key(cb_ctx)
            plugin._call_models[key] = "gemini-2.5-flash"

            response = FakeLlmResponse(
                usage_metadata=FakeUsageMetadata(100, 50),
            )
            await plugin.after_model_callback(cb_ctx, response)
            assert run_ctx.budget_remaining is not None
            assert run_ctx.budget_remaining == pytest.approx(1.0 - run_ctx.cost)

    async def test_trace_records_mode(self, plugin):
        init(mode="enforce")
        with run() as run_ctx:
            cb_ctx = FakeCallbackContext()
            key = plugin._callback_key(cb_ctx)
            plugin._call_models[key] = "gpt-4o"

            response = FakeLlmResponse(
                usage_metadata=FakeUsageMetadata(10, 10),
            )
            await plugin.after_model_callback(cb_ctx, response)
            trace = run_ctx.trace()
            assert len(trace) == 1
            assert trace[0]["reason"] == "enforce"
            assert trace[0]["model"] == "gpt-4o"

    async def test_no_start_time_records_zero_latency(self, plugin):
        init(mode="observe")
        with run() as run_ctx:
            cb_ctx = FakeCallbackContext()
            key = plugin._callback_key(cb_ctx)
            plugin._call_models[key] = "gpt-4o"
            # Don't set start time

            response = FakeLlmResponse(
                usage_metadata=FakeUsageMetadata(10, 10),
            )
            await plugin.after_model_callback(cb_ctx, response)
            assert run_ctx.latency_used_ms == 0.0

    async def test_fail_open_swallows_errors(self, plugin):
        init(mode="observe")
        with run():
            with patch(
                "cascadeflow.integrations.google_adk.get_current_run",
                side_effect=RuntimeError("boom"),
            ):
                result = await plugin.after_model_callback(
                    FakeCallbackContext(),
                    FakeLlmResponse(),
                )
                assert result is None


# ---------------------------------------------------------------------------
# on_model_error_callback
# ---------------------------------------------------------------------------


class TestOnModelErrorCallback:
    @pytest.fixture
    def plugin(self):
        return adk_mod.CascadeFlowADKPlugin()

    async def test_records_error_in_trace(self, plugin):
        init(mode="observe")
        with run() as run_ctx:
            cb_ctx = FakeCallbackContext()
            key = plugin._callback_key(cb_ctx)
            plugin._call_models[key] = "gemini-2.5-flash"
            plugin._call_start_times[key] = time.monotonic()

            await plugin.on_model_error_callback(cb_ctx, ValueError("bad input"))

            trace = run_ctx.trace()
            assert len(trace) == 1
            assert trace[0]["action"] == "error"
            assert "ValueError" in trace[0]["reason"]
            assert trace[0]["model"] == "gemini-2.5-flash"

    async def test_cleans_up_timing_state(self, plugin):
        init(mode="observe")
        with run():
            cb_ctx = FakeCallbackContext()
            key = plugin._callback_key(cb_ctx)
            plugin._call_models[key] = "gemini-2.5-flash"
            plugin._call_start_times[key] = time.monotonic()

            await plugin.on_model_error_callback(cb_ctx, RuntimeError("oops"))

            assert key not in plugin._call_models
            assert key not in plugin._call_start_times

    async def test_fail_open_swallows_errors(self, plugin):
        init(mode="observe")
        with run():
            with patch(
                "cascadeflow.integrations.google_adk.get_current_run",
                side_effect=RuntimeError("boom"),
            ):
                result = await plugin.on_model_error_callback(
                    FakeCallbackContext(),
                    ValueError("test"),
                )
                assert result is None


# ---------------------------------------------------------------------------
# enable / disable lifecycle
# ---------------------------------------------------------------------------


class TestEnableDisable:
    def test_enable_returns_plugin_instance(self):
        plugin = adk_mod.enable()
        assert isinstance(plugin, adk_mod.CascadeFlowADKPlugin)
        assert adk_mod.is_enabled()

    def test_enable_is_idempotent(self):
        p1 = adk_mod.enable()
        p2 = adk_mod.enable()
        assert p1 is p2  # same instance

    def test_enable_applies_config(self):
        config = adk_mod.GoogleADKHarnessConfig(fail_open=False, enable_budget_gate=False)
        plugin = adk_mod.enable(config=config)
        assert plugin._config.fail_open is False
        assert plugin._config.enable_budget_gate is False

    def test_disable_deactivates_plugin(self):
        plugin = adk_mod.enable()
        assert plugin._active is True
        adk_mod.disable()
        assert not adk_mod.is_enabled()
        assert plugin._active is False

    def test_disable_when_not_enabled_is_safe(self):
        adk_mod.disable()  # should not raise
        assert not adk_mod.is_enabled()


# ---------------------------------------------------------------------------
# Public API helpers
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_is_available_reflects_module_flag(self):
        assert adk_mod.is_available() == adk_mod.GOOGLE_ADK_AVAILABLE

    def test_is_enabled_default_false(self):
        assert adk_mod.is_enabled() is False

    def test_get_config_returns_copy(self):
        cfg = adk_mod.get_config()
        assert isinstance(cfg, adk_mod.GoogleADKHarnessConfig)
        assert cfg.fail_open is True
        assert cfg.enable_budget_gate is True
        # Modifying the copy doesn't affect module state
        cfg.fail_open = False
        assert adk_mod.get_config().fail_open is True


# ---------------------------------------------------------------------------
# GoogleADKHarnessConfig
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults(self):
        cfg = adk_mod.GoogleADKHarnessConfig()
        assert cfg.fail_open is True
        assert cfg.enable_budget_gate is True

    def test_custom_values(self):
        cfg = adk_mod.GoogleADKHarnessConfig(fail_open=False, enable_budget_gate=False)
        assert cfg.fail_open is False
        assert cfg.enable_budget_gate is False


# ---------------------------------------------------------------------------
# Plugin deactivate
# ---------------------------------------------------------------------------


class TestDeactivate:
    async def test_deactivated_plugin_skips_callbacks(self):
        plugin = adk_mod.CascadeFlowADKPlugin()
        plugin.deactivate()

        init(mode="enforce", budget=0.001)
        with run(budget=0.001) as run_ctx:
            run_ctx.cost = 0.002
            result = await plugin.before_model_callback(
                FakeCallbackContext(), FakeLlmRequest()
            )
            assert result is None  # no-op, not blocked

    async def test_deactivate_clears_state(self):
        plugin = adk_mod.CascadeFlowADKPlugin()
        plugin._call_start_times[12345] = 1.0
        plugin._call_models[12345] = "test"
        plugin.deactivate()
        assert len(plugin._call_start_times) == 0
        assert len(plugin._call_models) == 0


# ---------------------------------------------------------------------------
# _extract_tokens
# ---------------------------------------------------------------------------


class TestExtractTokens:
    def test_from_usage_metadata(self):
        response = FakeLlmResponse(
            usage_metadata=FakeUsageMetadata(100, 200),
        )
        assert adk_mod.CascadeFlowADKPlugin._extract_tokens(response) == (100, 200)

    def test_zero_usage_falls_back_to_content(self):
        response = FakeLlmResponse(
            usage_metadata=FakeUsageMetadata(0, 0),
            content=FakeContent(parts=[FakePart(text="x" * 80)]),
        )
        inp, out = adk_mod.CascadeFlowADKPlugin._extract_tokens(response)
        assert inp == 0
        assert out == 20  # 80 / 4

    def test_no_usage_no_content(self):
        response = FakeLlmResponse()
        assert adk_mod.CascadeFlowADKPlugin._extract_tokens(response) == (0, 0)

    def test_content_with_no_text(self):
        response = FakeLlmResponse(
            content=FakeContent(parts=[FakePart(function_call={"name": "f"})]),
        )
        inp, out = adk_mod.CascadeFlowADKPlugin._extract_tokens(response)
        assert inp == 0
        assert out == 1  # max(0//4, 1)


class TestCallbackKeyCollision:
    """Verify _callback_key uses id() for per-object uniqueness."""

    def test_distinct_keys_for_different_objects(self):
        """Two distinct context objects always produce distinct keys."""
        ctx_a = FakeCallbackContext(invocation_id="inv-1", agent_name="agent-a")
        ctx_b = FakeCallbackContext(invocation_id="inv-1", agent_name="agent-a")
        key_a = adk_mod.CascadeFlowADKPlugin._callback_key(ctx_a)
        key_b = adk_mod.CascadeFlowADKPlugin._callback_key(ctx_b)
        assert key_a != key_b, "Same IDs on different objects must produce distinct keys"

    def test_key_stable_for_same_object(self):
        """Same context object always produces the same key."""
        ctx = FakeCallbackContext()
        key1 = adk_mod.CascadeFlowADKPlugin._callback_key(ctx)
        key2 = adk_mod.CascadeFlowADKPlugin._callback_key(ctx)
        assert key1 == key2

    def test_key_is_int(self):
        """Key type is int (object id)."""
        ctx = FakeCallbackContext()
        assert isinstance(adk_mod.CascadeFlowADKPlugin._callback_key(ctx), int)

    @pytest.mark.asyncio
    async def test_concurrent_same_ids_track_independently(self):
        """Two concurrent calls with same invocation_id+agent_name don't corrupt."""
        init(mode="observe")
        with run(budget=1.0) as harness_ctx:
            plugin = adk_mod.CascadeFlowADKPlugin()
            # Same IDs — previously would collide
            ctx_a = FakeCallbackContext(invocation_id="inv-1", agent_name="agent")
            ctx_b = FakeCallbackContext(invocation_id="inv-1", agent_name="agent")

            req_a = FakeLlmRequest(model="gpt-4o")
            req_b = FakeLlmRequest(model="gpt-4o-mini")

            await plugin.before_model_callback(ctx_a, req_a)
            await plugin.before_model_callback(ctx_b, req_b)

            resp_b = FakeLlmResponse(usage_metadata=FakeUsageMetadata(50, 25))
            resp_a = FakeLlmResponse(usage_metadata=FakeUsageMetadata(100, 50))
            await plugin.after_model_callback(ctx_b, resp_b)
            await plugin.after_model_callback(ctx_a, resp_a)

            assert harness_ctx.step_count == 2
            assert len(plugin._call_start_times) == 0
            assert len(plugin._call_models) == 0


# ---------------------------------------------------------------------------
# Off-mode behavior
# ---------------------------------------------------------------------------


class TestOffMode:
    """mode='off' must not track metrics or update run context."""

    @pytest.mark.asyncio
    async def test_off_mode_before_callback_returns_none(self):
        init(mode="off")
        plugin = adk_mod.CascadeFlowADKPlugin()
        with run() as run_ctx:
            result = await plugin.before_model_callback(
                FakeCallbackContext(), FakeLlmRequest()
            )
            assert result is None
            assert len(plugin._call_start_times) == 0

    @pytest.mark.asyncio
    async def test_off_mode_after_callback_does_not_track(self):
        init(mode="off")
        plugin = adk_mod.CascadeFlowADKPlugin()
        with run() as run_ctx:
            await plugin.after_model_callback(
                FakeCallbackContext(),
                FakeLlmResponse(usage_metadata=FakeUsageMetadata(1000, 500)),
            )
            assert run_ctx.step_count == 0
            assert run_ctx.cost == 0.0
            assert run_ctx.energy_used == 0.0
            assert len(run_ctx.trace()) == 0


# ---------------------------------------------------------------------------
# Versioned model name resolution
# ---------------------------------------------------------------------------


class TestVersionedModelPricing:
    """Versioned model IDs must resolve to correct pricing, not default."""

    def test_versioned_gemini_flash(self):
        from cascadeflow.harness.pricing import estimate_cost

        # Should resolve to gemini-2.5-flash pricing ($0.15/$0.60)
        cost = estimate_cost("gemini-2.5-flash-preview-05-20", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.75, abs=0.01)

    def test_versioned_gemini_pro(self):
        from cascadeflow.harness.pricing import estimate_cost

        cost = estimate_cost("gemini-2.5-pro-preview-05-06", 1_000_000, 1_000_000)
        assert cost == pytest.approx(11.25, abs=0.01)

    def test_dated_model_suffix(self):
        from cascadeflow.harness.pricing import estimate_cost

        cost = estimate_cost("gemini-2.5-flash-20250120", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.75, abs=0.01)

    def test_latest_suffix(self):
        from cascadeflow.harness.pricing import estimate_cost

        cost = estimate_cost("gemini-2.5-flash-latest", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.75, abs=0.01)

    def test_unknown_model_still_uses_default(self):
        from cascadeflow.harness.pricing import estimate_cost

        cost = estimate_cost("totally-unknown-model", 1_000_000, 0)
        assert cost == pytest.approx(2.50)

    def test_exact_match_still_works(self):
        from cascadeflow.harness.pricing import estimate_cost

        cost = estimate_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.75, abs=0.01)

    def test_prefix_match_variant(self):
        """A variant like gemini-2.5-flash-8b matches the base model."""
        from cascadeflow.harness.pricing import estimate_cost

        cost = estimate_cost("gemini-2.5-flash-8b", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.75, abs=0.01)
