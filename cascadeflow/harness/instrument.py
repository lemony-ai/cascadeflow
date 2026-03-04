"""Python SDK auto-instrumentation for cascadeflow harness.

Patches OpenAI and Anthropic SDK request methods to intercept LLM calls for
observe/enforce modes.

This module is called internally by ``cascadeflow.harness.init()``. Users
should not call patch/unpatch helpers directly.

Implementation notes:
    - Patching is class-level (all current and future client instances).
    - Patching is idempotent (safe to call multiple times).
    - ``unpatch_openai()`` restores the original methods exactly.
    - Streaming responses are wrapped to capture usage after completion.
    - ``with_raw_response`` is NOT patched in V2 (known limitation).
"""

from __future__ import annotations

import functools
import logging
import time
from dataclasses import dataclass
from typing import Any

from cascadeflow.harness.pricing import (
    DEFAULT_ENERGY_COEFFICIENT as _DEFAULT_ENERGY_COEFFICIENT,
)
from cascadeflow.harness.pricing import (
    ENERGY_COEFFICIENTS as _ENERGY_COEFFICIENTS,
)
from cascadeflow.harness.pricing import (
    OPENAI_MODEL_POOL as _PRICING_MODELS,
)
from cascadeflow.harness.pricing import (
    estimate_cost as _estimate_cost_shared,
)
from cascadeflow.harness.pricing import (
    estimate_energy as _estimate_energy_shared,
)
from cascadeflow.harness.pricing import (
    model_total_price as _model_total_price_shared,
)

logger = logging.getLogger("cascadeflow.harness.instrument")

# ---------------------------------------------------------------------------
# Module-level state for idempotent patch/unpatch
# ---------------------------------------------------------------------------

_openai_patched: bool = False
_original_sync_create: Any = None
_original_async_create: Any = None
_anthropic_patched: bool = False
_original_anthropic_sync_create: Any = None
_original_anthropic_async_create: Any = None

_MODEL_TOTAL_COSTS: dict[str, float] = {
    name: _model_total_price_shared(name) for name in _PRICING_MODELS
}
_CHEAPEST_MODEL: str = min(_MODEL_TOTAL_COSTS, key=_MODEL_TOTAL_COSTS.get)
_MIN_TOTAL_COST: float = min(_MODEL_TOTAL_COSTS.values())
_MAX_TOTAL_COST: float = max(_MODEL_TOTAL_COSTS.values())

_OPENAI_ENERGY_COEFFS: dict[str, float] = {
    name: _ENERGY_COEFFICIENTS.get(name, _DEFAULT_ENERGY_COEFFICIENT) for name in _PRICING_MODELS
}
_LOWEST_ENERGY_MODEL: str = min(_OPENAI_ENERGY_COEFFS, key=_OPENAI_ENERGY_COEFFS.get)
_MIN_ENERGY_COEFF: float = min(_OPENAI_ENERGY_COEFFS.values())
_MAX_ENERGY_COEFF: float = max(_OPENAI_ENERGY_COEFFS.values())

# Relative priors used by KPI-weighted soft-control scoring.
# These are deterministic heuristics based on internal benchmark runs and
# intended as defaults until provider-specific online scoring is wired in.
_QUALITY_PRIORS: dict[str, float] = {
    "gpt-4o": 0.90,
    "gpt-4o-mini": 0.75,
    "gpt-5-mini": 0.86,
    "gpt-4-turbo": 0.88,
    "gpt-4": 0.87,
    "gpt-3.5-turbo": 0.65,
    "o1": 0.95,
    "o1-mini": 0.82,
    "o3-mini": 0.80,
}
_LATENCY_PRIORS: dict[str, float] = {
    "gpt-4o": 0.72,
    "gpt-4o-mini": 0.93,
    "gpt-5-mini": 0.84,
    "gpt-4-turbo": 0.66,
    "gpt-4": 0.52,
    "gpt-3.5-turbo": 1.00,
    "o1": 0.40,
    "o1-mini": 0.60,
    "o3-mini": 0.78,
}
_LATENCY_CANDIDATES: tuple[str, ...] = tuple(
    name for name in _PRICING_MODELS if name in _LATENCY_PRIORS
)
_FASTEST_MODEL: str | None = (
    max(_LATENCY_CANDIDATES, key=lambda name: _LATENCY_PRIORS[name])
    if _LATENCY_CANDIDATES
    else None
)

# OpenAI-model allowlists used by the current OpenAI harness instrumentation.
# Future provider instrumentation should provide provider-specific allowlists.
_COMPLIANCE_MODEL_ALLOWLISTS: dict[str, set[str]] = {
    "gdpr": {"gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"},
    "hipaa": {"gpt-4o", "gpt-4o-mini"},
    "pci": {"gpt-4o-mini", "gpt-3.5-turbo"},
    "strict": {"gpt-4o"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_stream_usage(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Inject ``stream_options.include_usage=True`` for streaming requests.

    OpenAI only sends usage data in the final stream chunk when this option
    is set.  Without it the harness would record zero cost for every
    streaming call.
    """
    if not kwargs.get("stream", False):
        return kwargs
    stream_options = kwargs.get("stream_options") or {}
    if not stream_options.get("include_usage"):
        stream_options = {**stream_options, "include_usage": True}
        kwargs = {**kwargs, "stream_options": stream_options}
    return kwargs


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost in USD from model name and token counts."""
    return _estimate_cost_shared(model, prompt_tokens, completion_tokens)


def _estimate_energy(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate energy units (deterministic proxy, not live carbon)."""
    return _estimate_energy_shared(model, prompt_tokens, completion_tokens)


def _count_tool_calls_in_openai_response(response: Any) -> int:
    """Count tool calls in a non-streaming ChatCompletion response."""
    choices = getattr(response, "choices", None)
    if not choices:
        return 0
    message = getattr(choices[0], "message", None)
    if message is None:
        return 0
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls is None:
        return 0
    return len(tool_calls)


def _extract_openai_usage(response: Any) -> tuple[int, int]:
    """Extract (prompt_tokens, completion_tokens) from a response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    return (
        getattr(usage, "prompt_tokens", 0) or 0,
        getattr(usage, "completion_tokens", 0) or 0,
    )


def _extract_anthropic_usage(response: Any) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from an Anthropic response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    return (
        getattr(usage, "input_tokens", 0) or 0,
        getattr(usage, "output_tokens", 0) or 0,
    )


def _count_tool_calls_in_anthropic_response(response: Any) -> int:
    """Count Anthropic ``tool_use`` blocks in a non-streaming response."""
    content = getattr(response, "content", None)
    if not content:
        return 0
    count = 0
    for block in content:
        if getattr(block, "type", None) == "tool_use":
            count += 1
    return count


def _model_total_cost(model: str) -> float:
    return _MODEL_TOTAL_COSTS.get(model, _model_total_price_shared(model))


def _select_cheaper_model(current_model: str) -> str:
    if _model_total_cost(_CHEAPEST_MODEL) < _model_total_cost(current_model):
        return _CHEAPEST_MODEL
    return current_model


def _select_faster_model(current_model: str) -> str:
    if _FASTEST_MODEL is None:
        return current_model
    current_latency = _LATENCY_PRIORS.get(current_model, 0.7)
    if _LATENCY_PRIORS[_FASTEST_MODEL] > current_latency:
        return _FASTEST_MODEL
    return current_model


def _select_lower_energy_model(current_model: str) -> str:
    if _ENERGY_COEFFICIENTS.get(
        _LOWEST_ENERGY_MODEL, _DEFAULT_ENERGY_COEFFICIENT
    ) < _ENERGY_COEFFICIENTS.get(
        current_model,
        _DEFAULT_ENERGY_COEFFICIENT,
    ):
        return _LOWEST_ENERGY_MODEL
    return current_model


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    normalized = {
        key: float(value)
        for key, value in weights.items()
        if key in {"cost", "quality", "latency", "energy"} and float(value) > 0
    }
    total = sum(normalized.values())
    if total <= 0:
        return {}
    return {key: value / total for key, value in normalized.items()}


def _cost_utility(model: str) -> float:
    model_cost = _model_total_cost(model)
    if _MAX_TOTAL_COST == _MIN_TOTAL_COST:
        return 1.0
    return (_MAX_TOTAL_COST - model_cost) / (_MAX_TOTAL_COST - _MIN_TOTAL_COST)


def _energy_utility(model: str) -> float:
    coeff = _ENERGY_COEFFICIENTS.get(model, _DEFAULT_ENERGY_COEFFICIENT)
    if _MAX_ENERGY_COEFF == _MIN_ENERGY_COEFF:
        return 1.0
    return (_MAX_ENERGY_COEFF - coeff) / (_MAX_ENERGY_COEFF - _MIN_ENERGY_COEFF)


def _kpi_score_with_normalized(model: str, normalized: dict[str, float]) -> float:
    if not normalized:
        return 0.0
    quality = _QUALITY_PRIORS.get(model, 0.7)
    latency = _LATENCY_PRIORS.get(model, 0.7)
    cost = _cost_utility(model)
    energy = _energy_utility(model)
    return (
        (normalized.get("quality", 0.0) * quality)
        + (normalized.get("latency", 0.0) * latency)
        + (normalized.get("cost", 0.0) * cost)
        + (normalized.get("energy", 0.0) * energy)
    )


def _kpi_score(model: str, weights: dict[str, float]) -> float:
    normalized = _normalize_weights(weights)
    return _kpi_score_with_normalized(model, normalized)


def _select_kpi_weighted_model(current_model: str, weights: dict[str, float]) -> str:
    normalized = _normalize_weights(weights)
    if not normalized:
        return current_model
    best_model = current_model
    best_score = _kpi_score_with_normalized(current_model, normalized)
    for candidate in _PRICING_MODELS:
        score = _kpi_score_with_normalized(candidate, normalized)
        if score > best_score:
            best_model = candidate
            best_score = score
    return best_model


def _compliance_allowlist(compliance: str | None) -> set[str] | None:
    if not compliance:
        return None
    return _COMPLIANCE_MODEL_ALLOWLISTS.get(compliance.strip().lower())


def _select_compliant_model(current_model: str, compliance: str) -> str | None:
    allowlist = _compliance_allowlist(compliance)
    if not allowlist:
        return current_model
    if current_model in allowlist:
        return current_model
    available = [name for name in _PRICING_MODELS if name in allowlist]
    if not available:
        return None
    return min(available, key=_model_total_cost)


@dataclass(frozen=True)
class _PreCallDecision:
    action: str
    reason: str
    target_model: str


def _evaluate_pre_call_decision(ctx: Any, model: str, has_tools: bool) -> _PreCallDecision:
    if ctx.budget_max is not None and ctx.cost >= ctx.budget_max:
        return _PreCallDecision(action="stop", reason="budget_exceeded", target_model=model)

    if has_tools and ctx.tool_calls_max is not None and ctx.tool_calls >= ctx.tool_calls_max:
        return _PreCallDecision(
            action="deny_tool", reason="max_tool_calls_reached", target_model=model
        )

    compliance = getattr(ctx, "compliance", None)
    if compliance:
        compliant_model = _select_compliant_model(model, str(compliance))
        if compliant_model is None:
            if has_tools:
                return _PreCallDecision(
                    action="deny_tool",
                    reason="compliance_no_approved_tool_path",
                    target_model=model,
                )
            return _PreCallDecision(
                action="stop", reason="compliance_no_approved_model", target_model=model
            )
        if compliant_model != model:
            return _PreCallDecision(
                action="switch_model",
                reason="compliance_model_policy",
                target_model=compliant_model,
            )
        if str(compliance).strip().lower() == "strict" and has_tools:
            return _PreCallDecision(
                action="deny_tool",
                reason="compliance_tool_restriction",
                target_model=model,
            )

    if ctx.latency_max_ms is not None and ctx.latency_used_ms >= ctx.latency_max_ms:
        faster_model = _select_faster_model(model)
        if faster_model != model:
            return _PreCallDecision(
                action="switch_model",
                reason="latency_limit_exceeded",
                target_model=faster_model,
            )
        return _PreCallDecision(action="stop", reason="latency_limit_exceeded", target_model=model)

    if ctx.energy_max is not None and ctx.energy_used >= ctx.energy_max:
        lower_energy_model = _select_lower_energy_model(model)
        if lower_energy_model != model:
            return _PreCallDecision(
                action="switch_model",
                reason="energy_limit_exceeded",
                target_model=lower_energy_model,
            )
        return _PreCallDecision(action="stop", reason="energy_limit_exceeded", target_model=model)

    if (
        ctx.budget_max is not None
        and ctx.budget_max > 0
        and ctx.budget_remaining is not None
        and (ctx.budget_remaining / ctx.budget_max) < 0.2
    ):
        cheaper_model = _select_cheaper_model(model)
        if cheaper_model != model:
            return _PreCallDecision(
                action="switch_model",
                reason="budget_pressure",
                target_model=cheaper_model,
            )

    kpi_weights = getattr(ctx, "kpi_weights", None)
    if isinstance(kpi_weights, dict) and kpi_weights:
        weighted_model = _select_kpi_weighted_model(model, kpi_weights)
        if weighted_model != model:
            return _PreCallDecision(
                action="switch_model",
                reason="kpi_weight_optimization",
                target_model=weighted_model,
            )

    return _PreCallDecision(action="allow", reason=ctx.mode, target_model=model)


def _raise_stop_error(ctx: Any, reason: str) -> None:
    from cascadeflow.schema.exceptions import BudgetExceededError, HarnessStopError

    if reason == "budget_exceeded":
        remaining = 0.0
        if ctx.budget_max is not None:
            remaining = ctx.budget_max - ctx.cost
        raise BudgetExceededError(
            f"Budget exhausted: spent ${ctx.cost:.4f} of ${ctx.budget_max or 0.0:.4f} max",
            remaining=remaining,
        )
    raise HarnessStopError(f"cascadeflow harness stop: {reason}", reason=reason)


def _resolve_pre_call_decision(
    ctx: Any,
    mode: str,
    model: str,
    kwargs: dict[str, Any],
) -> tuple[dict[str, Any], str, str, str, str, bool]:
    decision = _evaluate_pre_call_decision(ctx, model, has_tools=bool(kwargs.get("tools")))
    action = decision.action
    reason = decision.reason
    target_model = decision.target_model
    applied = action == "allow"

    if mode == "enforce":
        if action == "stop":
            ctx.record(
                action="stop",
                reason=reason,
                model=model,
                applied=True,
                decision_mode=mode,
            )
            _raise_stop_error(ctx, reason)

        if action == "switch_model" and target_model != model:
            kwargs = {**kwargs, "model": target_model}
            model = target_model
            applied = True
        elif action == "switch_model":
            applied = False

        if action == "deny_tool":
            if kwargs.get("tools"):
                kwargs = {**kwargs, "tools": []}
                applied = True
            else:
                applied = False
    elif action != "allow":
        logger.debug(
            "harness observe decision: action=%s reason=%s model=%s target=%s",
            action,
            reason,
            model,
            target_model,
        )
        applied = False

    return kwargs, model, action, reason, target_model, applied


def _update_context(
    ctx: Any,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    tool_call_count: int,
    elapsed_ms: float,
    *,
    action: str = "allow",
    action_reason: str | None = None,
    action_model: str | None = None,
    applied: bool | None = None,
    decision_mode: str | None = None,
) -> None:
    """Update a HarnessRunContext with call metrics."""
    cost = _estimate_cost(model, prompt_tokens, completion_tokens)
    energy = _estimate_energy(model, prompt_tokens, completion_tokens)

    ctx.cost += cost
    ctx.step_count += 1
    ctx.latency_used_ms += elapsed_ms
    ctx.energy_used += energy
    ctx.tool_calls += tool_call_count

    if ctx.budget_max is not None:
        ctx.budget_remaining = ctx.budget_max - ctx.cost

    if applied is None:
        applied = action == "allow"
    if decision_mode is None:
        decision_mode = ctx.mode

    if action == "allow":
        ctx.record(
            action="allow",
            reason=ctx.mode,
            model=model,
            applied=applied,
            decision_mode=decision_mode,
        )
        return

    ctx.record(
        action=action,
        reason=action_reason or ctx.mode,
        model=action_model or model,
        applied=applied,
        decision_mode=decision_mode,
    )


# ---------------------------------------------------------------------------
# Stream wrappers
# ---------------------------------------------------------------------------


class _InstrumentedStreamBase:
    """Shared stream-wrapper logic for sync and async OpenAI streams."""

    __slots__ = (
        "_stream",
        "_ctx",
        "_model",
        "_start_time",
        "_pre_action",
        "_pre_reason",
        "_pre_model",
        "_pre_applied",
        "_decision_mode",
        "_usage",
        "_tool_call_count",
        "_finalized",
    )

    def __init__(
        self,
        stream: Any,
        ctx: Any,
        model: str,
        start_time: float,
        pre_action: str = "allow",
        pre_reason: str = "observe",
        pre_model: str | None = None,
        pre_applied: bool = True,
        decision_mode: str = "observe",
    ) -> None:
        self._stream = stream
        self._ctx = ctx
        self._model = model
        self._start_time = start_time
        self._pre_action = pre_action
        self._pre_reason = pre_reason
        self._pre_model = pre_model or model
        self._pre_applied = pre_applied
        self._decision_mode = decision_mode
        self._usage: Any = None
        self._tool_call_count: int = 0
        self._finalized: bool = False

    def close(self) -> None:
        self._finalize()
        if hasattr(self._stream, "close"):
            self._stream.close()

    @property
    def response(self) -> Any:
        return getattr(self._stream, "response", None)

    def _inspect_chunk(self, chunk: Any) -> None:
        usage = getattr(chunk, "usage", None)
        if usage is not None:
            self._usage = usage

        choices = getattr(chunk, "choices", [])
        if choices:
            delta = getattr(choices[0], "delta", None)
            if delta:
                tool_calls = getattr(delta, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        # A new tool call has an ``id``; subsequent deltas for
                        # the same call only have ``index``.
                        if getattr(tc, "id", None):
                            self._tool_call_count += 1

    def _finalize(self) -> None:
        if self._finalized:
            return
        self._finalized = True

        if self._ctx is None:
            return

        elapsed_ms = (time.monotonic() - self._start_time) * 1000
        prompt_tokens = 0
        completion_tokens = 0
        if self._usage:
            prompt_tokens = getattr(self._usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(self._usage, "completion_tokens", 0) or 0

        _update_context(
            self._ctx,
            self._model,
            prompt_tokens,
            completion_tokens,
            self._tool_call_count,
            elapsed_ms,
            action=self._pre_action,
            action_reason=self._pre_reason,
            action_model=self._pre_model,
            applied=self._pre_applied,
            decision_mode=self._decision_mode,
        )


class _InstrumentedStream(_InstrumentedStreamBase):
    """Wraps an OpenAI sync ``Stream`` and tracks usage at stream end."""

    __slots__ = ()

    def __iter__(self) -> _InstrumentedStream:
        return self

    def __next__(self) -> Any:
        try:
            chunk = next(self._stream)
            self._inspect_chunk(chunk)
            return chunk
        except StopIteration:
            self._finalize()
            raise
        except Exception:
            self._finalize()
            raise

    def __enter__(self) -> _InstrumentedStream:
        if hasattr(self._stream, "__enter__"):
            self._stream.__enter__()
        return self

    def __exit__(self, *args: Any) -> bool:
        self._finalize()
        if hasattr(self._stream, "__exit__"):
            return self._stream.__exit__(*args)  # type: ignore[no-any-return]
        return False


class _InstrumentedAsyncStream(_InstrumentedStreamBase):
    """Wraps an OpenAI async ``AsyncStream`` and tracks usage at stream end."""

    __slots__ = ()

    def __aiter__(self) -> _InstrumentedAsyncStream:
        return self

    async def __anext__(self) -> Any:
        try:
            chunk = await self._stream.__anext__()
            self._inspect_chunk(chunk)
            return chunk
        except StopAsyncIteration:
            self._finalize()
            raise
        except Exception:
            self._finalize()
            raise

    async def __aenter__(self) -> _InstrumentedAsyncStream:
        if hasattr(self._stream, "__aenter__"):
            await self._stream.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool:
        self._finalize()
        if hasattr(self._stream, "__aexit__"):
            return await self._stream.__aexit__(*args)  # type: ignore[no-any-return]
        return False


class _InstrumentedAnthropicStreamBase:
    """Shared stream-wrapper logic for sync and async Anthropic streams."""

    __slots__ = (
        "_stream",
        "_ctx",
        "_model",
        "_start_time",
        "_pre_action",
        "_pre_reason",
        "_pre_model",
        "_pre_applied",
        "_decision_mode",
        "_input_tokens",
        "_output_tokens",
        "_tool_call_count",
        "_finalized",
    )

    def __init__(
        self,
        stream: Any,
        ctx: Any,
        model: str,
        start_time: float,
        pre_action: str = "allow",
        pre_reason: str = "observe",
        pre_model: str | None = None,
        pre_applied: bool = True,
        decision_mode: str = "observe",
    ) -> None:
        self._stream = stream
        self._ctx = ctx
        self._model = model
        self._start_time = start_time
        self._pre_action = pre_action
        self._pre_reason = pre_reason
        self._pre_model = pre_model or model
        self._pre_applied = pre_applied
        self._decision_mode = decision_mode
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._tool_call_count: int = 0
        self._finalized: bool = False

    def close(self) -> None:
        self._finalize()
        if hasattr(self._stream, "close"):
            self._stream.close()

    def _inspect_event(self, event: Any) -> None:
        event_type = getattr(event, "type", None)

        if event_type == "message_start":
            message = getattr(event, "message", None)
            usage = getattr(message, "usage", None)
            if usage is not None:
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)
                if isinstance(input_tokens, (int, float)):
                    self._input_tokens = int(input_tokens) if input_tokens > 0 else 0
                if isinstance(output_tokens, (int, float)):
                    self._output_tokens = int(output_tokens) if output_tokens > 0 else 0
            return

        usage = getattr(event, "usage", None)
        if usage is not None:
            input_tokens = getattr(usage, "input_tokens", None)
            output_tokens = getattr(usage, "output_tokens", None)
            if isinstance(input_tokens, (int, float)) and input_tokens > 0:
                self._input_tokens = int(input_tokens)
            if isinstance(output_tokens, (int, float)):
                self._output_tokens = int(output_tokens) if output_tokens > 0 else 0

        if event_type == "content_block_start":
            content_block = getattr(event, "content_block", None)
            block_type = getattr(content_block, "type", None)
            if block_type in {"tool_use", "server_tool_use"}:
                self._tool_call_count += 1

    def _finalize(self) -> None:
        if self._finalized:
            return
        self._finalized = True

        if self._ctx is None:
            return

        elapsed_ms = (time.monotonic() - self._start_time) * 1000
        _update_context(
            self._ctx,
            self._model,
            self._input_tokens,
            self._output_tokens,
            self._tool_call_count,
            elapsed_ms,
            action=self._pre_action,
            action_reason=self._pre_reason,
            action_model=self._pre_model,
            applied=self._pre_applied,
            decision_mode=self._decision_mode,
        )


class _InstrumentedAnthropicStream(_InstrumentedAnthropicStreamBase):
    """Wraps an Anthropic sync stream and tracks usage at stream end."""

    __slots__ = ()

    def __iter__(self) -> _InstrumentedAnthropicStream:
        return self

    def __next__(self) -> Any:
        try:
            event = next(self._stream)
            self._inspect_event(event)
            return event
        except StopIteration:
            self._finalize()
            raise
        except Exception:
            self._finalize()
            raise

    def __enter__(self) -> _InstrumentedAnthropicStream:
        if hasattr(self._stream, "__enter__"):
            self._stream.__enter__()
        return self

    def __exit__(self, *args: Any) -> bool:
        self._finalize()
        if hasattr(self._stream, "__exit__"):
            return self._stream.__exit__(*args)  # type: ignore[no-any-return]
        return False


class _InstrumentedAnthropicAsyncStream(_InstrumentedAnthropicStreamBase):
    """Wraps an Anthropic async stream and tracks usage at stream end."""

    __slots__ = ()

    def __aiter__(self) -> _InstrumentedAnthropicAsyncStream:
        return self

    async def __anext__(self) -> Any:
        try:
            event = await self._stream.__anext__()
            self._inspect_event(event)
            return event
        except StopAsyncIteration:
            self._finalize()
            raise
        except Exception:
            self._finalize()
            raise

    async def __aenter__(self) -> _InstrumentedAnthropicAsyncStream:
        if hasattr(self._stream, "__aenter__"):
            await self._stream.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool:
        self._finalize()
        if hasattr(self._stream, "__aexit__"):
            return await self._stream.__aexit__(*args)  # type: ignore[no-any-return]
        return False


# ---------------------------------------------------------------------------
# Wrapper factories
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CallInterceptionState:
    kwargs: dict[str, Any]
    model: str
    pre_action: str
    pre_reason: str
    pre_model: str
    pre_applied: bool
    is_stream: bool
    start_time: float


def _prepare_call_interception(
    *,
    ctx: Any,
    mode: str,
    kwargs: dict[str, Any],
) -> _CallInterceptionState:
    model: str = kwargs.get("model", "unknown")
    pre_action = "allow"
    pre_reason = mode
    pre_model = model
    pre_applied = True

    if ctx:
        kwargs, model, pre_action, pre_reason, pre_model, pre_applied = _resolve_pre_call_decision(
            ctx,
            mode,
            model,
            kwargs,
        )

    is_stream: bool = bool(kwargs.get("stream", False))
    kwargs = _ensure_stream_usage(kwargs)

    return _CallInterceptionState(
        kwargs=kwargs,
        model=model,
        pre_action=pre_action,
        pre_reason=pre_reason,
        pre_model=pre_model,
        pre_applied=pre_applied,
        is_stream=is_stream,
        start_time=time.monotonic(),
    )


def _finalize_interception(
    *,
    ctx: Any,
    mode: str,
    state: _CallInterceptionState,
    response: Any,
    stream_wrapper: type[_InstrumentedStream] | type[_InstrumentedAsyncStream],
) -> Any:
    if state.is_stream and ctx:
        return stream_wrapper(
            response,
            ctx,
            state.model,
            state.start_time,
            state.pre_action,
            state.pre_reason,
            state.pre_model,
            state.pre_applied,
            mode,
        )

    if (not state.is_stream) and ctx:
        elapsed_ms = (time.monotonic() - state.start_time) * 1000
        prompt_tokens, completion_tokens = _extract_openai_usage(response)
        tool_call_count = _count_tool_calls_in_openai_response(response)
        _update_context(
            ctx,
            state.model,
            prompt_tokens,
            completion_tokens,
            tool_call_count,
            elapsed_ms,
            action=state.pre_action,
            action_reason=state.pre_reason,
            action_model=state.pre_model,
            applied=state.pre_applied,
            decision_mode=mode,
        )
    else:
        logger.debug(
            "harness %s: model=%s (no active run scope, metrics not tracked)",
            mode,
            state.model,
        )

    return response


def _make_patched_create(original_fn: Any) -> Any:
    """Create a patched version of ``Completions.create``."""

    @functools.wraps(original_fn)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        from cascadeflow.harness.api import get_current_run, get_harness_config

        config = get_harness_config()
        ctx = get_current_run()
        mode = ctx.mode if ctx else config.mode

        if mode == "off":
            return original_fn(self, *args, **kwargs)

        state = _prepare_call_interception(ctx=ctx, mode=mode, kwargs=kwargs)

        logger.debug(
            "harness intercept: model=%s stream=%s mode=%s",
            state.model,
            state.is_stream,
            mode,
        )

        response = original_fn(self, *args, **state.kwargs)

        return _finalize_interception(
            ctx=ctx,
            mode=mode,
            state=state,
            response=response,
            stream_wrapper=_InstrumentedStream,
        )

    return wrapper


def _make_patched_async_create(original_fn: Any) -> Any:
    """Create a patched version of ``AsyncCompletions.create``."""

    @functools.wraps(original_fn)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        from cascadeflow.harness.api import get_current_run, get_harness_config

        config = get_harness_config()
        ctx = get_current_run()
        mode = ctx.mode if ctx else config.mode

        if mode == "off":
            return await original_fn(self, *args, **kwargs)

        state = _prepare_call_interception(ctx=ctx, mode=mode, kwargs=kwargs)

        logger.debug(
            "harness intercept async: model=%s stream=%s mode=%s",
            state.model,
            state.is_stream,
            mode,
        )

        response = await original_fn(self, *args, **state.kwargs)

        return _finalize_interception(
            ctx=ctx,
            mode=mode,
            state=state,
            response=response,
            stream_wrapper=_InstrumentedAsyncStream,
        )

    return wrapper


def _make_patched_anthropic_create(original_fn: Any) -> Any:
    """Create a patched version of ``anthropic.Messages.create``."""

    @functools.wraps(original_fn)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        from cascadeflow.harness.api import get_current_run, get_harness_config

        config = get_harness_config()
        ctx = get_current_run()
        mode = ctx.mode if ctx else config.mode

        if mode == "off":
            return original_fn(self, *args, **kwargs)

        model: str = kwargs.get("model", "unknown")
        pre_action = "allow"
        pre_reason = mode
        pre_model = model
        pre_applied = True

        if ctx:
            kwargs, model, pre_action, pre_reason, pre_model, pre_applied = (
                _resolve_pre_call_decision(
                    ctx,
                    mode,
                    model,
                    kwargs,
                )
            )

        is_stream = bool(kwargs.get("stream", False))
        start_time = time.monotonic()
        response = original_fn(self, *args, **kwargs)

        if not ctx:
            logger.debug(
                "harness %s (anthropic): model=%s (no active run scope, metrics not tracked)",
                mode,
                model,
            )
            return response

        if is_stream:
            return _InstrumentedAnthropicStream(
                response,
                ctx,
                model,
                start_time,
                pre_action,
                pre_reason,
                pre_model,
                pre_applied,
                mode,
            )

        elapsed_ms = (time.monotonic() - start_time) * 1000
        input_tokens, output_tokens = _extract_anthropic_usage(response)
        tool_call_count = _count_tool_calls_in_anthropic_response(response)
        _update_context(
            ctx,
            model,
            input_tokens,
            output_tokens,
            tool_call_count,
            elapsed_ms,
            action=pre_action,
            action_reason=pre_reason,
            action_model=pre_model,
            applied=pre_applied,
            decision_mode=mode,
        )
        return response

    return wrapper


def _make_patched_anthropic_async_create(original_fn: Any) -> Any:
    """Create a patched version of ``anthropic.AsyncMessages.create``."""

    @functools.wraps(original_fn)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        from cascadeflow.harness.api import get_current_run, get_harness_config

        config = get_harness_config()
        ctx = get_current_run()
        mode = ctx.mode if ctx else config.mode

        if mode == "off":
            return await original_fn(self, *args, **kwargs)

        model: str = kwargs.get("model", "unknown")
        pre_action = "allow"
        pre_reason = mode
        pre_model = model
        pre_applied = True

        if ctx:
            kwargs, model, pre_action, pre_reason, pre_model, pre_applied = (
                _resolve_pre_call_decision(
                    ctx,
                    mode,
                    model,
                    kwargs,
                )
            )

        is_stream = bool(kwargs.get("stream", False))
        start_time = time.monotonic()
        response = await original_fn(self, *args, **kwargs)

        if not ctx:
            logger.debug(
                "harness %s async (anthropic): model=%s (no active run scope, metrics not tracked)",
                mode,
                model,
            )
            return response

        if is_stream:
            return _InstrumentedAnthropicAsyncStream(
                response,
                ctx,
                model,
                start_time,
                pre_action,
                pre_reason,
                pre_model,
                pre_applied,
                mode,
            )

        elapsed_ms = (time.monotonic() - start_time) * 1000
        input_tokens, output_tokens = _extract_anthropic_usage(response)
        tool_call_count = _count_tool_calls_in_anthropic_response(response)
        _update_context(
            ctx,
            model,
            input_tokens,
            output_tokens,
            tool_call_count,
            elapsed_ms,
            action=pre_action,
            action_reason=pre_reason,
            action_model=pre_model,
            applied=pre_applied,
            decision_mode=mode,
        )
        return response

    return wrapper


# ---------------------------------------------------------------------------
# Public API (called by cascadeflow.harness.api)
# ---------------------------------------------------------------------------


def patch_openai() -> bool:
    """Patch the OpenAI Python client for harness instrumentation.

    Returns ``True`` if patching succeeded, ``False`` if openai is not
    installed.  Idempotent: safe to call multiple times.
    """
    global _openai_patched, _original_sync_create, _original_async_create

    if _openai_patched:
        logger.debug("openai already patched, skipping")
        return True

    try:
        from openai.resources.chat.completions import AsyncCompletions, Completions
    except ImportError:
        logger.debug("openai package not available, skipping instrumentation")
        return False

    _original_sync_create = Completions.create
    _original_async_create = AsyncCompletions.create

    Completions.create = _make_patched_create(_original_sync_create)  # type: ignore[assignment]
    AsyncCompletions.create = _make_patched_async_create(  # type: ignore[assignment]
        _original_async_create,
    )

    _openai_patched = True
    logger.info("openai client instrumented (sync + async)")
    return True


def patch_anthropic() -> bool:
    """Patch the Anthropic Python client for harness instrumentation.

    Returns ``True`` if patching succeeded, ``False`` if anthropic is not
    installed. Idempotent: safe to call multiple times.
    """
    global _anthropic_patched, _original_anthropic_sync_create, _original_anthropic_async_create

    if _anthropic_patched:
        logger.debug("anthropic already patched, skipping")
        return True

    try:
        from anthropic.resources.messages import AsyncMessages, Messages
    except ImportError:
        logger.debug("anthropic package not available, skipping instrumentation")
        return False

    _original_anthropic_sync_create = Messages.create
    _original_anthropic_async_create = AsyncMessages.create

    Messages.create = _make_patched_anthropic_create(_original_anthropic_sync_create)  # type: ignore[assignment]
    AsyncMessages.create = _make_patched_anthropic_async_create(  # type: ignore[assignment]
        _original_anthropic_async_create,
    )

    _anthropic_patched = True
    logger.info("anthropic client instrumented (sync + async)")
    return True


def unpatch_openai() -> None:
    """Restore original OpenAI client methods.

    Safe to call even if not patched.  Used by ``reset()`` and tests.
    """
    global _openai_patched, _original_sync_create, _original_async_create

    if not _openai_patched:
        return

    try:
        from openai.resources.chat.completions import AsyncCompletions, Completions
    except ImportError:
        _openai_patched = False
        return

    if _original_sync_create is not None:
        Completions.create = _original_sync_create  # type: ignore[assignment]
    if _original_async_create is not None:
        AsyncCompletions.create = _original_async_create  # type: ignore[assignment]

    _original_sync_create = None
    _original_async_create = None
    _openai_patched = False
    logger.info("openai client unpatched")


def unpatch_anthropic() -> None:
    """Restore original Anthropic client methods.

    Safe to call even if not patched. Used by ``reset()`` and tests.
    """
    global _anthropic_patched, _original_anthropic_sync_create, _original_anthropic_async_create

    if not _anthropic_patched:
        return

    try:
        from anthropic.resources.messages import AsyncMessages, Messages
    except ImportError:
        _anthropic_patched = False
        return

    if _original_anthropic_sync_create is not None:
        Messages.create = _original_anthropic_sync_create  # type: ignore[assignment]
    if _original_anthropic_async_create is not None:
        AsyncMessages.create = _original_anthropic_async_create  # type: ignore[assignment]

    _original_anthropic_sync_create = None
    _original_anthropic_async_create = None
    _anthropic_patched = False
    logger.info("anthropic client unpatched")


def is_openai_patched() -> bool:
    """Return whether the OpenAI client is currently patched."""
    return _openai_patched


def is_anthropic_patched() -> bool:
    """Return whether the Anthropic client is currently patched."""
    return _anthropic_patched


def is_patched() -> bool:
    """Return whether any supported Python SDK is currently patched."""
    return _openai_patched or _anthropic_patched
