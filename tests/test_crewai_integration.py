"""Tests for cascadeflow.integrations.crewai harness integration.

crewai is not installed in test environments, so we mock the hooks module
and test the integration logic directly against HarnessRunContext.
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

import pytest

from cascadeflow.harness import get_current_run, init, reset, run

# Import the module directly — it does not require crewai at import time
# (CREWAI_AVAILABLE will be False, but all functions/classes are still defined).
import cascadeflow.integrations.crewai as crewai_mod


@pytest.fixture(autouse=True)
def _reset_crewai_state():
    """Reset harness and crewai module state before every test."""
    reset()
    crewai_mod._hooks_registered = False
    crewai_mod._before_hook_ref = None
    crewai_mod._after_hook_ref = None
    crewai_mod._config = crewai_mod.CrewAIHarnessConfig()
    crewai_mod._call_start_times.clear()
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeLLM:
    """Minimal stand-in for a CrewAI LLM object."""

    def __init__(self, model: str = "gpt-4o"):
        self.model = model


class FakeMessage:
    """Minimal stand-in for a CrewAI message object."""

    def __init__(self, content: str):
        self.content = content


class FakeHookContext:
    """Minimal stand-in for crewai's LLMCallHookContext."""

    def __init__(
        self,
        *,
        llm: FakeLLM | None = None,
        messages: list | None = None,
        response: str | None = None,
    ):
        self.llm = llm or FakeLLM()
        self.messages = messages or []
        self.response = response


def _make_fake_hooks_module():
    """Build a fake crewai.hooks module with recording registration helpers."""
    mod = types.ModuleType("crewai.hooks")
    mod._before_hooks = []
    mod._after_hooks = []
    mod.register_before_llm_call_hook = lambda fn: mod._before_hooks.append(fn)
    mod.register_after_llm_call_hook = lambda fn: mod._after_hooks.append(fn)
    mod.unregister_before_llm_call_hook = lambda fn: (
        mod._before_hooks.remove(fn) if fn in mod._before_hooks else None
    )
    mod.unregister_after_llm_call_hook = lambda fn: (
        mod._after_hooks.remove(fn) if fn in mod._after_hooks else None
    )
    return mod


# ---------------------------------------------------------------------------
# _extract_model_name
# ---------------------------------------------------------------------------


class TestExtractModelName:
    def test_extracts_plain_model(self):
        ctx = FakeHookContext(llm=FakeLLM("gpt-4o"))
        assert crewai_mod._extract_model_name(ctx) == "gpt-4o"

    def test_strips_provider_prefix(self):
        ctx = FakeHookContext(llm=FakeLLM("openai/gpt-4o-mini"))
        assert crewai_mod._extract_model_name(ctx) == "gpt-4o-mini"

    def test_no_llm_returns_unknown(self):
        ctx = FakeHookContext()
        ctx.llm = None
        assert crewai_mod._extract_model_name(ctx) == "unknown"

    def test_no_model_attr_returns_unknown(self):
        ctx = FakeHookContext()
        ctx.llm = object()  # no .model attribute
        assert crewai_mod._extract_model_name(ctx) == "unknown"

    def test_non_string_model_returns_unknown(self):
        ctx = FakeHookContext()
        ctx.llm = FakeLLM("gpt-4o")
        ctx.llm.model = 42  # not a string
        assert crewai_mod._extract_model_name(ctx) == "unknown"


# ---------------------------------------------------------------------------
# Cost / energy estimation
# ---------------------------------------------------------------------------


class TestEstimation:
    def test_estimate_cost_known_model(self):
        cost = crewai_mod._estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.15 + 0.60)

    def test_estimate_cost_unknown_model_uses_default(self):
        cost = crewai_mod._estimate_cost("unknown-model", 1_000_000, 0)
        assert cost == pytest.approx(2.50)

    def test_estimate_energy_known_model(self):
        energy = crewai_mod._estimate_energy("gpt-4o", 100, 100)
        # coeff=1.0, output_weight=1.5
        assert energy == pytest.approx(1.0 * (100 + 100 * 1.5))

    def test_estimate_energy_unknown_model(self):
        energy = crewai_mod._estimate_energy("unknown-model", 100, 100)
        assert energy == pytest.approx(1.0 * (100 + 100 * 1.5))


# ---------------------------------------------------------------------------
# before_llm_call_hook
# ---------------------------------------------------------------------------


class TestBeforeHook:
    def test_no_run_context_returns_none(self):
        ctx = FakeHookContext()
        result = crewai_mod._before_llm_call_hook(ctx)
        assert result is None

    def test_observe_mode_allows(self):
        init(mode="observe", budget=0.001)
        with run(budget=0.001) as run_ctx:
            run_ctx.cost = 0.002  # over budget
            hook_ctx = FakeHookContext()
            result = crewai_mod._before_llm_call_hook(hook_ctx)
            # observe mode never blocks
            assert result is None

    def test_enforce_blocks_when_budget_exhausted(self):
        init(mode="enforce", budget=0.001)
        with run(budget=0.001) as run_ctx:
            run_ctx.cost = 0.001  # exactly at budget
            hook_ctx = FakeHookContext(llm=FakeLLM("gpt-4o"))
            result = crewai_mod._before_llm_call_hook(hook_ctx)
            assert result is False
            assert run_ctx.last_action == "stop"
            trace = run_ctx.trace()
            assert trace[-1]["reason"] == "budget_exhausted"

    def test_enforce_allows_when_under_budget(self):
        init(mode="enforce", budget=1.0)
        with run(budget=1.0) as run_ctx:
            run_ctx.cost = 0.5
            hook_ctx = FakeHookContext()
            result = crewai_mod._before_llm_call_hook(hook_ctx)
            assert result is None

    def test_records_start_time(self):
        init(mode="observe")
        with run() as run_ctx:
            hook_ctx = FakeHookContext()
            crewai_mod._before_llm_call_hook(hook_ctx)
            assert id(hook_ctx) in crewai_mod._call_start_times

    def test_budget_gate_disabled_in_config(self):
        crewai_mod._config = crewai_mod.CrewAIHarnessConfig(enable_budget_gate=False)
        init(mode="enforce", budget=0.001)
        with run(budget=0.001) as run_ctx:
            run_ctx.cost = 0.002
            hook_ctx = FakeHookContext()
            result = crewai_mod._before_llm_call_hook(hook_ctx)
            assert result is None  # gate disabled, not blocked

    def test_fail_open_swallows_errors(self):
        crewai_mod._config = crewai_mod.CrewAIHarnessConfig(fail_open=True)
        init(mode="enforce")
        with run() as run_ctx:
            hook_ctx = FakeHookContext()
            with patch(
                "cascadeflow.harness.api.get_current_run",
                side_effect=RuntimeError("boom"),
            ):
                result = crewai_mod._before_llm_call_hook(hook_ctx)
                assert result is None  # fail_open returns None

    def test_fail_closed_raises_errors(self):
        crewai_mod._config = crewai_mod.CrewAIHarnessConfig(fail_open=False)
        init(mode="enforce")
        with run():
            hook_ctx = FakeHookContext()
            with patch(
                "cascadeflow.harness.api.get_current_run",
                side_effect=RuntimeError("boom"),
            ):
                with pytest.raises(RuntimeError, match="boom"):
                    crewai_mod._before_llm_call_hook(hook_ctx)


# ---------------------------------------------------------------------------
# after_llm_call_hook
# ---------------------------------------------------------------------------


class TestAfterHook:
    def test_no_run_context_returns_none(self):
        ctx = FakeHookContext(response="hello")
        result = crewai_mod._after_llm_call_hook(ctx)
        assert result is None

    def test_updates_run_metrics(self):
        init(mode="observe")
        with run(budget=1.0) as run_ctx:
            hook_ctx = FakeHookContext(
                llm=FakeLLM("gpt-4o-mini"),
                messages=[FakeMessage("What is 2+2?")],
                response="The answer is 4.",
            )
            # Simulate before hook setting start time
            crewai_mod._call_start_times[id(hook_ctx)] = __import__("time").monotonic() - 0.1

            crewai_mod._after_llm_call_hook(hook_ctx)

            assert run_ctx.step_count == 1
            assert run_ctx.cost > 0
            assert run_ctx.energy_used > 0
            assert run_ctx.latency_used_ms > 0
            assert run_ctx.model_used == "gpt-4o-mini"
            assert run_ctx.last_action == "allow"

    def test_updates_budget_remaining(self):
        init(mode="enforce", budget=1.0)
        with run(budget=1.0) as run_ctx:
            hook_ctx = FakeHookContext(
                llm=FakeLLM("gpt-4o"),
                messages=[FakeMessage("test")],
                response="response",
            )
            crewai_mod._after_llm_call_hook(hook_ctx)
            assert run_ctx.budget_remaining is not None
            assert run_ctx.budget_remaining == pytest.approx(1.0 - run_ctx.cost)

    def test_trace_records_mode(self):
        init(mode="enforce")
        with run() as run_ctx:
            hook_ctx = FakeHookContext(
                llm=FakeLLM("gpt-4o"),
                messages=[FakeMessage("test")],
                response="done",
            )
            crewai_mod._after_llm_call_hook(hook_ctx)
            trace = run_ctx.trace()
            assert len(trace) == 1
            assert trace[0]["reason"] == "enforce"
            assert trace[0]["model"] == "gpt-4o"

    def test_no_start_time_records_zero_latency(self):
        init(mode="observe")
        with run() as run_ctx:
            hook_ctx = FakeHookContext(
                llm=FakeLLM("gpt-4o"),
                messages=[],
                response="ok",
            )
            # Don't set start time
            crewai_mod._after_llm_call_hook(hook_ctx)
            assert run_ctx.latency_used_ms == 0.0

    def test_token_estimation_from_chars(self):
        init(mode="observe")
        with run() as run_ctx:
            # 400 chars in messages → 100 prompt tokens
            # 80 chars in response → 20 completion tokens
            messages = [FakeMessage("x" * 400)]
            hook_ctx = FakeHookContext(
                llm=FakeLLM("gpt-4o"),
                messages=messages,
                response="y" * 80,
            )
            crewai_mod._after_llm_call_hook(hook_ctx)
            # gpt-4o: $2.50/1M in, $10.00/1M out
            expected_cost = (100 / 1_000_000) * 2.50 + (20 / 1_000_000) * 10.00
            assert run_ctx.cost == pytest.approx(expected_cost)

    def test_fail_open_swallows_errors(self):
        crewai_mod._config = crewai_mod.CrewAIHarnessConfig(fail_open=True)
        init(mode="observe")
        with run() as run_ctx:
            hook_ctx = FakeHookContext(response="ok")
            with patch(
                "cascadeflow.harness.api.get_current_run",
                side_effect=RuntimeError("boom"),
            ):
                result = crewai_mod._after_llm_call_hook(hook_ctx)
                assert result is None


# ---------------------------------------------------------------------------
# enable / disable lifecycle
# ---------------------------------------------------------------------------


class TestEnableDisable:
    def test_enable_returns_false_when_crewai_not_available(self):
        with patch.object(crewai_mod, "CREWAI_AVAILABLE", False):
            result = crewai_mod.enable()
            assert result is False
            assert not crewai_mod.is_enabled()

    def test_enable_registers_hooks(self, monkeypatch):
        fake_hooks = _make_fake_hooks_module()
        monkeypatch.setattr(crewai_mod, "CREWAI_AVAILABLE", True)

        # Make the import inside enable() find our fake module
        import sys

        monkeypatch.setitem(sys.modules, "crewai.hooks", fake_hooks)

        result = crewai_mod.enable()
        assert result is True
        assert crewai_mod.is_enabled()
        assert len(fake_hooks._before_hooks) == 1
        assert len(fake_hooks._after_hooks) == 1

    def test_enable_is_idempotent(self, monkeypatch):
        fake_hooks = _make_fake_hooks_module()
        monkeypatch.setattr(crewai_mod, "CREWAI_AVAILABLE", True)

        import sys

        monkeypatch.setitem(sys.modules, "crewai.hooks", fake_hooks)

        crewai_mod.enable()
        crewai_mod.enable()  # second call
        assert len(fake_hooks._before_hooks) == 1  # still just one

    def test_enable_applies_config(self, monkeypatch):
        fake_hooks = _make_fake_hooks_module()
        monkeypatch.setattr(crewai_mod, "CREWAI_AVAILABLE", True)

        import sys

        monkeypatch.setitem(sys.modules, "crewai.hooks", fake_hooks)

        custom_config = crewai_mod.CrewAIHarnessConfig(fail_open=False, enable_budget_gate=False)
        crewai_mod.enable(config=custom_config)

        cfg = crewai_mod.get_config()
        assert cfg.fail_open is False
        assert cfg.enable_budget_gate is False

    def test_disable_unregisters_hooks(self, monkeypatch):
        fake_hooks = _make_fake_hooks_module()
        monkeypatch.setattr(crewai_mod, "CREWAI_AVAILABLE", True)

        import sys

        monkeypatch.setitem(sys.modules, "crewai.hooks", fake_hooks)

        crewai_mod.enable()
        assert crewai_mod.is_enabled()
        assert len(fake_hooks._before_hooks) == 1

        crewai_mod.disable()
        assert not crewai_mod.is_enabled()
        assert len(fake_hooks._before_hooks) == 0
        assert len(fake_hooks._after_hooks) == 0

    def test_disable_when_not_enabled_is_safe(self):
        crewai_mod.disable()  # should not raise
        assert not crewai_mod.is_enabled()

    def test_disable_clears_call_start_times(self, monkeypatch):
        fake_hooks = _make_fake_hooks_module()
        monkeypatch.setattr(crewai_mod, "CREWAI_AVAILABLE", True)

        import sys

        monkeypatch.setitem(sys.modules, "crewai.hooks", fake_hooks)

        crewai_mod.enable()
        crewai_mod._call_start_times[123] = 1.0
        crewai_mod.disable()
        assert len(crewai_mod._call_start_times) == 0

    def test_enable_returns_false_for_old_crewai(self, monkeypatch):
        """When crewai is installed but lacks hooks module (< v1.5)."""
        monkeypatch.setattr(crewai_mod, "CREWAI_AVAILABLE", True)

        import sys

        # Remove crewai.hooks from modules so import fails
        monkeypatch.delitem(sys.modules, "crewai.hooks", raising=False)
        # Also ensure the import fails
        import importlib

        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "crewai.hooks":
                raise ImportError("no hooks")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)

        result = crewai_mod.enable()
        assert result is False


# ---------------------------------------------------------------------------
# Public API helpers
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_is_available_reflects_module_flag(self):
        # crewai is not installed in test env
        assert crewai_mod.is_available() == crewai_mod.CREWAI_AVAILABLE

    def test_is_enabled_default_false(self):
        assert crewai_mod.is_enabled() is False

    def test_get_config_returns_copy(self):
        cfg = crewai_mod.get_config()
        assert isinstance(cfg, crewai_mod.CrewAIHarnessConfig)
        assert cfg.fail_open is True
        assert cfg.enable_budget_gate is True
        # Modifying the copy doesn't affect the module state
        cfg.fail_open = False
        assert crewai_mod.get_config().fail_open is True


# ---------------------------------------------------------------------------
# CrewAIHarnessConfig
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults(self):
        cfg = crewai_mod.CrewAIHarnessConfig()
        assert cfg.fail_open is True
        assert cfg.enable_budget_gate is True

    def test_custom_values(self):
        cfg = crewai_mod.CrewAIHarnessConfig(fail_open=False, enable_budget_gate=False)
        assert cfg.fail_open is False
        assert cfg.enable_budget_gate is False
