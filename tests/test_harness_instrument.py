"""Tests for cascadeflow.harness.instrument — OpenAI auto-instrumentation."""

from __future__ import annotations

import time
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from cascadeflow.harness import init, reset, run
from cascadeflow.harness.instrument import (
    _InstrumentedAsyncStream,
    _InstrumentedStream,
    _estimate_cost,
    _estimate_energy,
    _make_patched_async_create,
    _make_patched_create,
    is_patched,
    patch_openai,
    unpatch_openai,
)


@pytest.fixture(autouse=True)
def _reset_harness() -> None:
    reset()
    yield  # type: ignore[misc]
    reset()


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_usage(prompt_tokens: int = 100, completion_tokens: int = 50) -> MagicMock:
    u = MagicMock()
    u.prompt_tokens = prompt_tokens
    u.completion_tokens = completion_tokens
    return u


def _mock_completion(
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    tool_calls: Optional[list] = None,
) -> MagicMock:
    msg = MagicMock()
    msg.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.usage = _mock_usage(prompt_tokens, completion_tokens)
    resp.choices = [choice]
    return resp


def _mock_tool_call(tc_id: str) -> MagicMock:
    tc = MagicMock()
    tc.id = tc_id
    return tc


def _mock_stream_chunk(
    content: str = "hi",
    usage: Optional[MagicMock] = None,
    tool_calls: Optional[list] = None,
) -> MagicMock:
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = tool_calls
    choice = MagicMock()
    choice.delta = delta
    chunk = MagicMock()
    chunk.choices = [choice]
    chunk.usage = usage
    return chunk


# ---------------------------------------------------------------------------
# Patch lifecycle
# ---------------------------------------------------------------------------


class TestPatchLifecycle:
    def test_patch_and_unpatch(self) -> None:
        assert not is_patched()
        result = patch_openai()
        assert result is True
        assert is_patched()
        unpatch_openai()
        assert not is_patched()

    def test_idempotent_patching(self) -> None:
        patch_openai()
        patch_openai()
        assert is_patched()
        unpatch_openai()
        assert not is_patched()

    def test_unpatch_without_prior_patch(self) -> None:
        unpatch_openai()  # should not raise

    def test_init_observe_patches(self) -> None:
        report = init(mode="observe")
        assert "openai" in report.instrumented
        assert is_patched()

    def test_init_enforce_patches(self) -> None:
        report = init(mode="enforce")
        assert "openai" in report.instrumented
        assert is_patched()

    def test_init_off_does_not_patch(self) -> None:
        init(mode="off")
        assert not is_patched()

    def test_reset_unpatches(self) -> None:
        init(mode="observe")
        assert is_patched()
        reset()
        assert not is_patched()

    def test_class_method_actually_replaced(self) -> None:
        from openai.resources.chat.completions import Completions

        original = Completions.create
        patch_openai()
        assert Completions.create is not original
        unpatch_openai()
        assert Completions.create is original


# ---------------------------------------------------------------------------
# Sync wrapper
# ---------------------------------------------------------------------------


class TestSyncWrapper:
    def test_observe_passes_through_response(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion()
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=1.0) as ctx:
            result = wrapper(MagicMock(), model="gpt-4o-mini")

        assert result is mock_resp
        original.assert_called_once()

    def test_observe_tracks_cost(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=10.0) as ctx:
            wrapper(MagicMock(), model="gpt-4o-mini")

        # gpt-4o-mini: $0.15/1M in + $0.60/1M out = $0.75
        assert ctx.cost == pytest.approx(0.75, abs=0.01)

    def test_observe_tracks_step_count(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion()
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=1.0) as ctx:
            wrapper(MagicMock(), model="gpt-4o-mini")
            wrapper(MagicMock(), model="gpt-4o-mini")

        assert ctx.step_count == 2

    def test_observe_tracks_tool_calls(self) -> None:
        init(mode="observe")
        tc1 = _mock_tool_call("tc_1")
        tc2 = _mock_tool_call("tc_2")
        mock_resp = _mock_completion(tool_calls=[tc1, tc2])
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=1.0) as ctx:
            wrapper(MagicMock(), model="gpt-4o")

        assert ctx.tool_calls == 2

    def test_observe_tracks_energy(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion(prompt_tokens=1000, completion_tokens=500)
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=1.0) as ctx:
            wrapper(MagicMock(), model="gpt-4o-mini")

        # gpt-4o-mini coefficient=0.3, output_weight=1.5
        # energy = 0.3 * (1000 + 500 * 1.5) = 0.3 * 1750 = 525.0
        assert ctx.energy_used == pytest.approx(525.0)

    def test_observe_tracks_latency(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion()
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=1.0) as ctx:
            wrapper(MagicMock(), model="gpt-4o-mini")

        assert ctx.latency_used_ms > 0

    def test_budget_remaining_decreases(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=10.0) as ctx:
            wrapper(MagicMock(), model="gpt-4o-mini")

        assert ctx.budget_remaining is not None
        assert ctx.budget_remaining < 10.0
        assert ctx.budget_remaining == pytest.approx(10.0 - 0.75, abs=0.01)

    def test_model_used_and_trace(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion()
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=1.0) as ctx:
            wrapper(MagicMock(), model="gpt-4o")

        assert ctx.model_used == "gpt-4o"
        trace = ctx.trace()
        assert len(trace) == 1
        assert trace[0]["action"] == "allow"
        assert trace[0]["reason"] == "observe"
        assert trace[0]["model"] == "gpt-4o"

    def test_off_mode_passthrough_no_tracking(self) -> None:
        init(mode="off")
        mock_resp = _mock_completion()
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run() as ctx:
            result = wrapper(MagicMock(), model="gpt-4o")

        assert result is mock_resp
        assert ctx.cost == 0.0
        assert ctx.step_count == 0

    def test_no_run_scope_logs_but_does_not_track(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion()
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        # Call outside any run() scope
        result = wrapper(MagicMock(), model="gpt-4o")
        assert result is mock_resp

    def test_multiple_calls_accumulate(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=10.0) as ctx:
            wrapper(MagicMock(), model="gpt-4o-mini")
            wrapper(MagicMock(), model="gpt-4o-mini")

        assert ctx.cost == pytest.approx(1.50, abs=0.01)
        assert ctx.step_count == 2
        assert len(ctx.trace()) == 2


# ---------------------------------------------------------------------------
# Async wrapper
# ---------------------------------------------------------------------------


class TestAsyncWrapper:
    @pytest.mark.asyncio
    async def test_observe_passes_through_response(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion()
        original = AsyncMock(return_value=mock_resp)
        wrapper = _make_patched_async_create(original)

        async with run(budget=1.0) as ctx:
            result = await wrapper(MagicMock(), model="gpt-4o")

        assert result is mock_resp

    @pytest.mark.asyncio
    async def test_observe_tracks_cost(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        original = AsyncMock(return_value=mock_resp)
        wrapper = _make_patched_async_create(original)

        async with run(budget=10.0) as ctx:
            await wrapper(MagicMock(), model="gpt-4o-mini")

        assert ctx.cost == pytest.approx(0.75, abs=0.01)
        assert ctx.step_count == 1

    @pytest.mark.asyncio
    async def test_off_mode_passthrough(self) -> None:
        init(mode="off")
        mock_resp = _mock_completion()
        original = AsyncMock(return_value=mock_resp)
        wrapper = _make_patched_async_create(original)

        async with run() as ctx:
            result = await wrapper(MagicMock(), model="gpt-4o")

        assert result is mock_resp
        assert ctx.cost == 0.0


# ---------------------------------------------------------------------------
# Sync stream wrapper
# ---------------------------------------------------------------------------


class TestSyncStreamWrapper:
    def test_stream_yields_all_chunks(self) -> None:
        init(mode="observe")
        chunk1 = _mock_stream_chunk("Hello")
        chunk2 = _mock_stream_chunk(" world", usage=_mock_usage(100, 50))
        mock_stream = iter([chunk1, chunk2])

        with run(budget=1.0) as ctx:
            wrapped = _InstrumentedStream(mock_stream, ctx, "gpt-4o-mini", time.monotonic())
            chunks = list(wrapped)

        assert len(chunks) == 2
        assert chunks[0] is chunk1
        assert chunks[1] is chunk2

    def test_stream_tracks_cost_after_consumption(self) -> None:
        init(mode="observe")
        chunk1 = _mock_stream_chunk("Hello")
        chunk2 = _mock_stream_chunk(" world", usage=_mock_usage(1_000_000, 1_000_000))
        mock_stream = iter([chunk1, chunk2])

        with run(budget=10.0) as ctx:
            wrapped = _InstrumentedStream(mock_stream, ctx, "gpt-4o-mini", time.monotonic())
            list(wrapped)

        assert ctx.cost == pytest.approx(0.75, abs=0.01)
        assert ctx.step_count == 1

    def test_stream_tracks_tool_calls(self) -> None:
        init(mode="observe")
        tc = _mock_tool_call("tc_1")
        chunk1 = _mock_stream_chunk("", tool_calls=[tc])
        chunk2 = _mock_stream_chunk("", usage=_mock_usage(100, 50))
        mock_stream = iter([chunk1, chunk2])

        with run(budget=1.0) as ctx:
            wrapped = _InstrumentedStream(mock_stream, ctx, "gpt-4o", time.monotonic())
            list(wrapped)

        assert ctx.tool_calls == 1

    def test_stream_context_manager(self) -> None:
        init(mode="observe")
        chunk1 = _mock_stream_chunk("data", usage=_mock_usage(100, 50))
        mock_inner = MagicMock()
        mock_inner.__iter__ = MagicMock(return_value=iter([chunk1]))
        mock_inner.__next__ = MagicMock(side_effect=[chunk1, StopIteration])
        mock_inner.__enter__ = MagicMock(return_value=mock_inner)
        mock_inner.__exit__ = MagicMock(return_value=False)

        with run(budget=1.0) as ctx:
            with _InstrumentedStream(mock_inner, ctx, "gpt-4o-mini", time.monotonic()) as stream:
                for _ in stream:
                    pass

        assert ctx.step_count == 1

    def test_stream_finalize_is_idempotent(self) -> None:
        init(mode="observe")
        chunk1 = _mock_stream_chunk("data", usage=_mock_usage(100, 50))
        mock_stream = iter([chunk1])

        with run(budget=1.0) as ctx:
            wrapped = _InstrumentedStream(mock_stream, ctx, "gpt-4o-mini", time.monotonic())
            list(wrapped)
            # Force finalize again
            wrapped._finalize()

        assert ctx.step_count == 1  # Should not double-count

    def test_stream_wrapper_via_patched_create(self) -> None:
        """Verify that stream=True in the wrapper returns an _InstrumentedStream."""
        init(mode="observe")
        chunk = _mock_stream_chunk("hi", usage=_mock_usage(50, 25))
        mock_stream = iter([chunk])
        original = MagicMock(return_value=mock_stream)
        wrapper = _make_patched_create(original)

        with run(budget=1.0) as ctx:
            result = wrapper(MagicMock(), model="gpt-4o-mini", stream=True)
            assert isinstance(result, _InstrumentedStream)
            list(result)

        assert ctx.step_count == 1


# ---------------------------------------------------------------------------
# Async stream wrapper
# ---------------------------------------------------------------------------


class TestAsyncStreamWrapper:
    @pytest.mark.asyncio
    async def test_async_stream_yields_all_chunks(self) -> None:
        init(mode="observe")
        chunk1 = _mock_stream_chunk("Hello")
        chunk2 = _mock_stream_chunk(" world", usage=_mock_usage(100, 50))

        async def _async_iter():
            yield chunk1
            yield chunk2

        mock_stream = _async_iter()

        async with run(budget=1.0) as ctx:
            wrapped = _InstrumentedAsyncStream(mock_stream, ctx, "gpt-4o-mini", time.monotonic())
            chunks = [c async for c in wrapped]

        assert len(chunks) == 2
        assert ctx.cost > 0
        assert ctx.step_count == 1

    @pytest.mark.asyncio
    async def test_async_stream_via_patched_create(self) -> None:
        """Verify that stream=True in async wrapper returns an _InstrumentedAsyncStream."""
        init(mode="observe")
        chunk = _mock_stream_chunk("hi", usage=_mock_usage(50, 25))

        async def _async_iter():
            yield chunk

        mock_stream = _async_iter()
        original = AsyncMock(return_value=mock_stream)
        wrapper = _make_patched_async_create(original)

        async with run(budget=1.0) as ctx:
            result = await wrapper(MagicMock(), model="gpt-4o-mini", stream=True)
            assert isinstance(result, _InstrumentedAsyncStream)
            _ = [c async for c in result]

        assert ctx.step_count == 1


# ---------------------------------------------------------------------------
# Cost and energy estimation
# ---------------------------------------------------------------------------


class TestEstimation:
    def test_cost_known_model(self) -> None:
        cost = _estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
        assert cost == pytest.approx(0.15 + 0.60)

    def test_cost_unknown_model_uses_default(self) -> None:
        cost = _estimate_cost("my-custom-model", 1_000_000, 1_000_000)
        # default pricing: $2.50/$10.00
        assert cost == pytest.approx(2.50 + 10.00)

    def test_cost_zero_tokens(self) -> None:
        cost = _estimate_cost("gpt-4o", 0, 0)
        assert cost == 0.0

    def test_energy_known_model(self) -> None:
        energy = _estimate_energy("gpt-4o-mini", 1000, 500)
        # coeff=0.3, output_weight=1.5
        # energy = 0.3 * (1000 + 500 * 1.5) = 0.3 * 1750 = 525.0
        assert energy == pytest.approx(525.0)

    def test_energy_unknown_model_uses_default(self) -> None:
        energy = _estimate_energy("custom-model", 1000, 500)
        # default coeff=1.0
        # energy = 1.0 * (1000 + 500 * 1.5) = 1750.0
        assert energy == pytest.approx(1750.0)


# ---------------------------------------------------------------------------
# Nested run isolation
# ---------------------------------------------------------------------------


class TestNestedRuns:
    def test_inner_run_does_not_affect_outer(self) -> None:
        init(mode="observe")
        mock_resp = _mock_completion(prompt_tokens=1_000_000, completion_tokens=1_000_000)
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=10.0) as outer:
            wrapper(MagicMock(), model="gpt-4o-mini")  # $0.75 to outer
            outer_cost_before_inner = outer.cost

            with run(budget=5.0) as inner:
                wrapper(MagicMock(), model="gpt-4o-mini")  # $0.75 to inner

            # Outer cost should be unchanged after inner scope exits
            assert outer.cost == pytest.approx(outer_cost_before_inner)
            assert inner.cost == pytest.approx(0.75, abs=0.01)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_response_without_usage(self) -> None:
        init(mode="observe")
        mock_resp = MagicMock()
        mock_resp.usage = None
        mock_resp.choices = []
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=1.0) as ctx:
            wrapper(MagicMock(), model="gpt-4o")

        assert ctx.cost == 0.0
        assert ctx.step_count == 1

    def test_response_without_choices(self) -> None:
        init(mode="observe")
        mock_resp = MagicMock()
        mock_resp.usage = _mock_usage(100, 50)
        mock_resp.choices = []
        original = MagicMock(return_value=mock_resp)
        wrapper = _make_patched_create(original)

        with run(budget=1.0) as ctx:
            wrapper(MagicMock(), model="gpt-4o")

        assert ctx.tool_calls == 0
        assert ctx.cost > 0

    def test_stream_without_usage_in_any_chunk(self) -> None:
        init(mode="observe")
        chunk1 = _mock_stream_chunk("Hello")
        chunk2 = _mock_stream_chunk(" world")
        mock_stream = iter([chunk1, chunk2])

        with run(budget=1.0) as ctx:
            wrapped = _InstrumentedStream(mock_stream, ctx, "gpt-4o-mini", time.monotonic())
            list(wrapped)

        assert ctx.cost == 0.0  # No usage data available
        assert ctx.step_count == 1  # Step still counted
