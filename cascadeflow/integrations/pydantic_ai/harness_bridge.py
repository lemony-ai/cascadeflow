"""Harness metrics bridge for the cascadeflow PydanticAI integration.

Records cost, latency, energy, and tool call metrics on the active
HarnessRunContext.  Also enforces budget gates in enforce mode.
"""

from __future__ import annotations

import logging

from cascadeflow.harness import get_current_run
from cascadeflow.harness.pricing import estimate_cost, estimate_energy
from cascadeflow.schema.exceptions import BudgetExceededError

logger = logging.getLogger("cascadeflow.integrations.pydantic_ai.harness_bridge")


def check_budget_gate(model_name: str, fail_open: bool = True) -> None:
    """Pre-call budget gate.  Raises BudgetExceededError in enforce mode.

    Args:
        model_name: Model about to be called (for logging)
        fail_open: If True, swallow internal errors instead of propagating
    """
    try:
        ctx = get_current_run()
        if ctx is None or ctx.mode == "off":
            return

        if ctx.mode == "enforce":
            if ctx.budget_remaining is not None and ctx.budget_remaining <= 0:
                ctx.record("stop", "budget_exceeded", model_name)
                raise BudgetExceededError(
                    "cascadeflow harness budget exceeded",
                    remaining=ctx.budget_remaining,
                )
    except BudgetExceededError:
        raise
    except Exception:
        if not fail_open:
            raise
        logger.debug("pydantic-ai budget gate check failed (fail-open)")


def record_metrics(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    elapsed_ms: float,
    tool_calls_count: int = 0,
    is_stream: bool = False,
    fail_open: bool = True,
) -> None:
    """Post-call: update HarnessRunContext with cost/latency/energy/tool_calls.

    Args:
        model_name: Model that was called
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens produced
        elapsed_ms: Elapsed time in milliseconds
        tool_calls_count: Number of tool calls in response
        is_stream: Whether this was a streaming call
        fail_open: If True, swallow internal errors
    """
    try:
        ctx = get_current_run()
        if ctx is None or ctx.mode == "off":
            return

        cost = estimate_cost(model_name, input_tokens, output_tokens)
        energy = estimate_energy(model_name, input_tokens, output_tokens)

        ctx.step_count += 1
        ctx.latency_used_ms += elapsed_ms
        ctx.energy_used += energy
        ctx.cost += cost
        if tool_calls_count > 0:
            ctx.tool_calls += tool_calls_count

        if ctx.budget_max is not None:
            ctx.budget_remaining = ctx.budget_max - ctx.cost

        ctx.model_used = model_name

        action = "allow"
        reason = "pydantic_ai_stream_step" if is_stream else "pydantic_ai_step"
        ctx.record(action, reason, model_name)

        if ctx.mode == "enforce" and ctx.budget_remaining is not None and ctx.budget_remaining <= 0:
            logger.info("pydantic-ai step exhausted budget; next step will be blocked")
    except Exception:
        if not fail_open:
            raise
        logger.debug("pydantic-ai harness metric update failed (fail-open)")
