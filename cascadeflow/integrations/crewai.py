"""CrewAI harness integration for cascadeflow.

Uses CrewAI's native ``llm_hooks`` system (v1.5+) to intercept all LLM calls
inside Crew executions, feeding metrics into ``cascadeflow.harness`` run
contexts.

This module is optional — ``pip install cascadeflow[crewai]`` pulls in the
crewai dependency.  When crewai is not installed the public helpers return
gracefully and ``CREWAI_AVAILABLE`` is ``False``.

Integration surface:
    - ``enable()``:  register before/after LLM-call hooks globally
    - ``disable()``: unregister hooks and clean up
    - ``CrewAIHarnessConfig``: optional knobs (fail_open, cost_model_override)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any, Callable, Optional

logger = logging.getLogger("cascadeflow.integrations.crewai")

CREWAI_AVAILABLE = find_spec("crewai") is not None

# ---------------------------------------------------------------------------
# Pricing table (USD per 1M tokens: input, output)
# Shared with instrument.py — kept small and self-contained to avoid
# cross-module coupling.  A future pricing registry will deduplicate.
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
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-3.5": (1.00, 5.00),
    "claude-opus-4.5": (5.00, 25.00),
}
_DEFAULT_PRICING: tuple[float, float] = (2.50, 10.00)

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


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    per_million = _PRICING.get(model, _DEFAULT_PRICING)
    return (prompt_tokens / 1_000_000) * per_million[0] + (completion_tokens / 1_000_000) * per_million[1]


def _estimate_energy(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    coeff = _ENERGY_COEFFICIENTS.get(model, _DEFAULT_ENERGY_COEFFICIENT)
    return coeff * (prompt_tokens + completion_tokens * _ENERGY_OUTPUT_WEIGHT)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class CrewAIHarnessConfig:
    """Runtime configuration for the CrewAI harness integration.

    fail_open:
        If ``True`` (default), errors inside hooks never break the CrewAI
        execution — they are logged and swallowed.
    enable_budget_gate:
        If ``True`` (default), a ``before_llm_call`` hook blocks calls when
        the harness run budget is exhausted (enforce mode only).
    """

    fail_open: bool = True
    enable_budget_gate: bool = True


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_config: CrewAIHarnessConfig = CrewAIHarnessConfig()
_hooks_registered: bool = False
_before_hook_ref: Any = None
_after_hook_ref: Any = None
# Track call start times per thread via a dict keyed by id(context)
_call_start_times: dict[int, float] = {}


# ---------------------------------------------------------------------------
# Hook implementations
# ---------------------------------------------------------------------------


def _extract_model_name(context: Any) -> str:
    """Best-effort extraction of the model name from a LLMCallHookContext."""
    llm = getattr(context, "llm", None)
    if llm is None:
        return "unknown"
    # CrewAI LLM objects have a .model attribute
    model = getattr(llm, "model", None)
    if isinstance(model, str):
        # Strip provider prefix like "openai/gpt-4o" → "gpt-4o"
        if "/" in model:
            return model.rsplit("/", 1)[-1]
        return model
    return "unknown"


def _before_llm_call_hook(context: Any) -> Optional[bool]:
    """Harness before-LLM-call hook registered with CrewAI.

    - In enforce mode with budget gate: blocks calls when budget exhausted.
    - Tracks call start time for latency measurement.
    - Returns ``None`` (allow) or ``False`` (block).
    """
    try:
        from cascadeflow.harness.api import get_current_run

        ctx = get_current_run()
        if ctx is None:
            return None

        # Record start time for latency tracking
        _call_start_times[id(context)] = time.monotonic()

        # Budget gate in enforce mode
        if (
            _config.enable_budget_gate
            and ctx.mode == "enforce"
            and ctx.budget_max is not None
            and ctx.cost >= ctx.budget_max
        ):
            logger.warning(
                "crewai hook: blocking LLM call — budget exhausted "
                "(spent $%.4f of $%.4f max)",
                ctx.cost,
                ctx.budget_max,
            )
            ctx.record(action="stop", reason="budget_exhausted", model=_extract_model_name(context))
            return False

        return None
    except Exception:
        if _config.fail_open:
            logger.debug("crewai before_llm_call hook error (fail_open)", exc_info=True)
            return None
        raise


def _after_llm_call_hook(context: Any) -> Optional[str]:
    """Harness after-LLM-call hook registered with CrewAI.

    Updates the active HarnessRunContext with:
    - cost (estimated from model + response length)
    - latency
    - energy estimate
    - step count
    - trace record

    Returns ``None`` (keep original response).
    """
    try:
        from cascadeflow.harness.api import get_current_run

        ctx = get_current_run()
        if ctx is None:
            return None

        model = _extract_model_name(context)
        response = getattr(context, "response", None) or ""

        # Estimate tokens from response text (rough: 1 token ≈ 4 chars)
        # CrewAI hooks don't expose raw token counts, so we approximate.
        messages = getattr(context, "messages", [])
        prompt_chars = sum(len(str(getattr(m, "content", "") or "")) for m in messages)
        completion_chars = len(str(response))
        prompt_tokens = max(prompt_chars // 4, 1)
        completion_tokens = max(completion_chars // 4, 1)

        cost = _estimate_cost(model, prompt_tokens, completion_tokens)
        energy = _estimate_energy(model, prompt_tokens, completion_tokens)

        # Latency
        start_time = _call_start_times.pop(id(context), None)
        elapsed_ms = (time.monotonic() - start_time) * 1000 if start_time else 0.0

        ctx.cost += cost
        ctx.step_count += 1
        ctx.latency_used_ms += elapsed_ms
        ctx.energy_used += energy

        if ctx.budget_max is not None:
            ctx.budget_remaining = ctx.budget_max - ctx.cost

        ctx.model_used = model
        ctx.record(action="allow", reason=ctx.mode, model=model)

        logger.debug(
            "crewai hook: tracked call model=%s cost=$%.6f latency=%.0fms",
            model,
            cost,
            elapsed_ms,
        )

        return None
    except Exception:
        if _config.fail_open:
            logger.debug("crewai after_llm_call hook error (fail_open)", exc_info=True)
            return None
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_available() -> bool:
    """Return whether the crewai package is installed."""
    return CREWAI_AVAILABLE


def is_enabled() -> bool:
    """Return whether harness hooks are currently registered with CrewAI."""
    return _hooks_registered


def enable(config: Optional[CrewAIHarnessConfig] = None) -> bool:
    """Register cascadeflow harness hooks with CrewAI's global hook system.

    Idempotent: safe to call multiple times.

    Args:
        config: Optional configuration overrides.

    Returns:
        ``True`` if hooks were registered, ``False`` if crewai is not
        installed.
    """
    global _config, _hooks_registered, _before_hook_ref, _after_hook_ref

    if _hooks_registered:
        logger.debug("crewai harness hooks already registered")
        return True

    if not CREWAI_AVAILABLE:
        logger.debug("crewai not installed, skipping hook registration")
        return False

    if config is not None:
        _config = config

    try:
        from crewai.hooks import (
            register_before_llm_call_hook,
            register_after_llm_call_hook,
        )
    except ImportError:
        logger.warning(
            "crewai is installed but hooks module not available "
            "(requires crewai>=1.5); skipping"
        )
        return False

    _before_hook_ref = _before_llm_call_hook
    _after_hook_ref = _after_llm_call_hook

    register_before_llm_call_hook(_before_hook_ref)
    register_after_llm_call_hook(_after_hook_ref)

    _hooks_registered = True
    logger.info("crewai harness hooks registered (before + after llm call)")
    return True


def disable() -> None:
    """Unregister cascadeflow harness hooks from CrewAI.

    Safe to call even if not enabled.
    """
    global _hooks_registered, _before_hook_ref, _after_hook_ref

    if not _hooks_registered:
        return

    try:
        from crewai.hooks import (
            unregister_before_llm_call_hook,
            unregister_after_llm_call_hook,
        )

        if _before_hook_ref is not None:
            unregister_before_llm_call_hook(_before_hook_ref)
        if _after_hook_ref is not None:
            unregister_after_llm_call_hook(_after_hook_ref)
    except ImportError:
        pass

    _before_hook_ref = None
    _after_hook_ref = None
    _hooks_registered = False
    _call_start_times.clear()
    logger.info("crewai harness hooks unregistered")


def get_config() -> CrewAIHarnessConfig:
    """Return a copy of the current configuration."""
    return CrewAIHarnessConfig(
        fail_open=_config.fail_open,
        enable_budget_gate=_config.enable_budget_gate,
    )
