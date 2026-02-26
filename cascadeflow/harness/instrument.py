"""OpenAI Python client auto-instrumentation for cascadeflow harness.

Patches ``openai.resources.chat.completions.Completions.create`` (sync) and
``AsyncCompletions.create`` (async) to intercept LLM calls for observe/enforce
modes.

This module is called internally by ``cascadeflow.harness.init()``.  Users
should not call ``patch_openai`` / ``unpatch_openai`` directly.

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
from typing import Any

logger = logging.getLogger("cascadeflow.harness.instrument")

# ---------------------------------------------------------------------------
# Module-level state for idempotent patch/unpatch
# ---------------------------------------------------------------------------

_openai_patched: bool = False
_original_sync_create: Any = None
_original_async_create: Any = None

# ---------------------------------------------------------------------------
# Pricing table (USD per 1M tokens: input, output)
# ---------------------------------------------------------------------------

_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-5-mini": (0.20, 0.80),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (1.10, 4.40),
}
_DEFAULT_PRICING: tuple[float, float] = (2.50, 10.00)

# ---------------------------------------------------------------------------
# Energy estimation coefficients (deterministic proxy, not live carbon data)
# energy_units = coefficient * (input_tokens + output_tokens * output_weight)
# ---------------------------------------------------------------------------

_ENERGY_COEFFICIENTS: dict[str, float] = {
    "gpt-4o": 1.0,
    "gpt-4o-mini": 0.3,
    "gpt-5-mini": 0.35,
    "gpt-4-turbo": 1.5,
    "gpt-4": 1.5,
    "gpt-3.5-turbo": 0.2,
    "o1": 2.0,
    "o1-mini": 0.8,
    "o3-mini": 0.5,
}
_DEFAULT_ENERGY_COEFFICIENT: float = 1.0
_ENERGY_OUTPUT_WEIGHT: float = 1.5

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
    per_million = _PRICING.get(model, _DEFAULT_PRICING)
    input_cost = (prompt_tokens / 1_000_000) * per_million[0]
    output_cost = (completion_tokens / 1_000_000) * per_million[1]
    return input_cost + output_cost


def _estimate_energy(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate energy units (deterministic proxy, not live carbon)."""
    coeff = _ENERGY_COEFFICIENTS.get(model, _DEFAULT_ENERGY_COEFFICIENT)
    return coeff * (prompt_tokens + completion_tokens * _ENERGY_OUTPUT_WEIGHT)


def _count_tool_calls_in_response(response: Any) -> int:
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


def _extract_usage(response: Any) -> tuple[int, int]:
    """Extract (prompt_tokens, completion_tokens) from a response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    return (
        getattr(usage, "prompt_tokens", 0) or 0,
        getattr(usage, "completion_tokens", 0) or 0,
    )


def _check_budget_pre_call(ctx: Any) -> None:
    """Raise BudgetExceededError in enforce mode if budget is already exhausted."""
    if ctx.mode != "enforce":
        return
    if ctx.budget_max is not None and ctx.cost >= ctx.budget_max:
        from cascadeflow.schema.exceptions import BudgetExceededError

        remaining = ctx.budget_max - ctx.cost
        raise BudgetExceededError(
            f"Budget exhausted: spent ${ctx.cost:.4f} of ${ctx.budget_max:.4f} max",
            remaining=remaining,
        )


def _update_context(
    ctx: Any,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    tool_call_count: int,
    elapsed_ms: float,
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

    ctx.model_used = model
    ctx.record(action="allow", reason=ctx.mode, model=model)


# ---------------------------------------------------------------------------
# Stream wrappers
# ---------------------------------------------------------------------------


class _InstrumentedStream:
    """Wraps an OpenAI ``Stream`` to capture usage after all chunks are consumed."""

    __slots__ = (
        "_stream",
        "_ctx",
        "_model",
        "_start_time",
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
    ) -> None:
        self._stream = stream
        self._ctx = ctx
        self._model = model
        self._start_time = start_time
        self._usage: Any = None
        self._tool_call_count: int = 0
        self._finalized: bool = False

    # --- iteration ---------------------------------------------------------

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

    # --- context manager ---------------------------------------------------

    def __enter__(self) -> _InstrumentedStream:
        if hasattr(self._stream, "__enter__"):
            self._stream.__enter__()
        return self

    def __exit__(self, *args: Any) -> bool:
        self._finalize()
        if hasattr(self._stream, "__exit__"):
            return self._stream.__exit__(*args)  # type: ignore[no-any-return]
        return False

    # --- proxied attributes ------------------------------------------------

    def close(self) -> None:
        self._finalize()
        if hasattr(self._stream, "close"):
            self._stream.close()

    @property
    def response(self) -> Any:
        return getattr(self._stream, "response", None)

    # --- internals ---------------------------------------------------------

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
                        # A new tool call has an ``id``; subsequent deltas
                        # for the same call only have ``index``.
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
        )


class _InstrumentedAsyncStream:
    """Wraps an OpenAI ``AsyncStream`` to capture usage after consumption."""

    __slots__ = (
        "_stream",
        "_ctx",
        "_model",
        "_start_time",
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
    ) -> None:
        self._stream = stream
        self._ctx = ctx
        self._model = model
        self._start_time = start_time
        self._usage: Any = None
        self._tool_call_count: int = 0
        self._finalized: bool = False

    # --- async iteration ---------------------------------------------------

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

    # --- async context manager ---------------------------------------------

    async def __aenter__(self) -> _InstrumentedAsyncStream:
        if hasattr(self._stream, "__aenter__"):
            await self._stream.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool:
        self._finalize()
        if hasattr(self._stream, "__aexit__"):
            return await self._stream.__aexit__(*args)  # type: ignore[no-any-return]
        return False

    # --- proxied attributes ------------------------------------------------

    def close(self) -> None:
        self._finalize()
        if hasattr(self._stream, "close"):
            self._stream.close()

    @property
    def response(self) -> Any:
        return getattr(self._stream, "response", None)

    # --- internals ---------------------------------------------------------

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
        )


# ---------------------------------------------------------------------------
# Wrapper factories
# ---------------------------------------------------------------------------


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

        model: str = kwargs.get("model", "unknown")
        is_stream: bool = bool(kwargs.get("stream", False))

        if ctx:
            _check_budget_pre_call(ctx)

        start_time = time.monotonic()

        kwargs = _ensure_stream_usage(kwargs)

        logger.debug("harness intercept: model=%s stream=%s mode=%s", model, is_stream, mode)

        response = original_fn(self, *args, **kwargs)

        if is_stream and ctx:
            return _InstrumentedStream(response, ctx, model, start_time)
        elif not is_stream and ctx:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            prompt_tokens, completion_tokens = _extract_usage(response)
            tool_call_count = _count_tool_calls_in_response(response)
            _update_context(
                ctx,
                model,
                prompt_tokens,
                completion_tokens,
                tool_call_count,
                elapsed_ms,
            )
        else:
            logger.debug(
                "harness %s: model=%s (no active run scope, metrics not tracked)",
                mode,
                model,
            )

        return response

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

        model: str = kwargs.get("model", "unknown")
        is_stream: bool = bool(kwargs.get("stream", False))

        if ctx:
            _check_budget_pre_call(ctx)

        start_time = time.monotonic()

        kwargs = _ensure_stream_usage(kwargs)

        logger.debug(
            "harness intercept async: model=%s stream=%s mode=%s",
            model,
            is_stream,
            mode,
        )

        response = await original_fn(self, *args, **kwargs)

        if is_stream and ctx:
            return _InstrumentedAsyncStream(response, ctx, model, start_time)
        elif not is_stream and ctx:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            prompt_tokens, completion_tokens = _extract_usage(response)
            tool_call_count = _count_tool_calls_in_response(response)
            _update_context(
                ctx,
                model,
                prompt_tokens,
                completion_tokens,
                tool_call_count,
                elapsed_ms,
            )
        else:
            logger.debug(
                "harness %s: model=%s (no active run scope, metrics not tracked)",
                mode,
                model,
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


def is_patched() -> bool:
    """Return whether the OpenAI client is currently patched."""
    return _openai_patched
