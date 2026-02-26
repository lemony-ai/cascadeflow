"""Harness-aware callbacks for LangChain/LangGraph integration.

Enforce-mode limitations (LangChain callback architecture):
    - ``stop`` (budget/latency/energy exceeded): fully enforced — raises
      BudgetExceededError or HarnessStopError from ``on_llm_start``.
    - ``deny_tool`` (tool-call cap): fully enforced at the tool level via
      ``on_tool_start`` — raises HarnessStopError before tool execution.
    - ``switch_model``: **observe-only** — LangChain dispatches the LLM call
      before ``on_llm_start`` returns, so the callback cannot redirect to a
      different model.  The decision is recorded with ``applied=False``.
    - ``deny_tool`` at LLM level (pre-call decision): **observe-only** — the
      callback cannot strip tools from an already-dispatched LLM request.
      The decision is recorded with ``applied=False``.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Optional

from cascadeflow.harness import get_current_run
from cascadeflow.harness.pricing import estimate_cost, estimate_energy
from cascadeflow.schema.exceptions import HarnessStopError

from .harness_state import apply_langgraph_state, extract_langgraph_state
from .langchain_callbacks import CascadeFlowCallbackHandler
from .utils import extract_token_usage, extract_tool_calls

logger = logging.getLogger("cascadeflow.harness.langchain")


class HarnessAwareCascadeFlowCallbackHandler(CascadeFlowCallbackHandler):
    """LangChain callback that bridges native lifecycle events into HarnessRunContext.

    See module docstring for enforce-mode limitations on ``switch_model``
    and LLM-level ``deny_tool``.
    """

    def __init__(self, *, fail_open: bool = True):
        super().__init__()
        self.fail_open = fail_open
        self._llm_started_at: Optional[float] = None
        self._pre_action: str = "allow"
        self._pre_reason: str = "allow"
        self._pre_model: Optional[str] = None
        self._pre_recorded: bool = False

    def _handle_harness_error(self, error: Exception) -> None:
        if self.fail_open:
            logger.exception("langchain harness callback failed (fail-open)", exc_info=error)
            return
        raise error

    def _sync_state(self, payload: dict[str, Any]) -> None:
        run_ctx = get_current_run()
        if run_ctx is None:
            return
        state = extract_langgraph_state(payload)
        if state:
            apply_langgraph_state(run_ctx, state)

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        super().on_llm_start(serialized=serialized, prompts=prompts, **kwargs)
        self._llm_started_at = time.monotonic()
        self._pre_action = "allow"
        self._pre_reason = "allow"
        self._pre_model = self.current_model
        self._pre_recorded = False

        try:
            self._sync_state(kwargs)

            run_ctx = get_current_run()
            if run_ctx is None:
                return

            model_name = self.current_model or "unknown"
            invocation_params = kwargs.get("invocation_params")
            has_tools = False
            if isinstance(invocation_params, dict):
                has_tools = bool(invocation_params.get("tools"))
            if not has_tools:
                has_tools = bool(kwargs.get("tools"))

            from cascadeflow.harness.instrument import _evaluate_pre_call_decision, _raise_stop_error  # noqa: I001

            decision = _evaluate_pre_call_decision(run_ctx, model_name, has_tools=has_tools)
            self._pre_action = decision.action
            self._pre_reason = decision.reason
            self._pre_model = decision.target_model

            if run_ctx.mode == "observe":
                if decision.action != "allow":
                    run_ctx.record(
                        action=decision.action,
                        reason=decision.reason,
                        model=decision.target_model,
                        applied=False,
                        decision_mode="observe",
                    )
                    self._pre_recorded = True
                return

            if run_ctx.mode != "enforce":
                return

            if decision.action == "stop":
                run_ctx.record(
                    action="stop",
                    reason=decision.reason,
                    model=model_name,
                    applied=True,
                    decision_mode="enforce",
                )
                self._pre_recorded = True
                _raise_stop_error(run_ctx, decision.reason)

            if decision.action == "switch_model":
                run_ctx.record(
                    action="switch_model",
                    reason=decision.reason,
                    model=decision.target_model,
                    applied=False,
                    decision_mode="enforce",
                )
                self._pre_recorded = True

            if decision.action == "deny_tool" and has_tools:
                run_ctx.record(
                    action="deny_tool",
                    reason=decision.reason,
                    model=model_name,
                    applied=False,
                    decision_mode="enforce",
                )
                self._pre_recorded = True

        except Exception as exc:
            self._handle_harness_error(exc)

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        super().on_llm_end(response=response, **kwargs)

        try:
            self._sync_state(kwargs)
            run_ctx = get_current_run()
            if run_ctx is None:
                return

            model_name = self.current_model
            if not model_name and getattr(response, "llm_output", None):
                model_name = response.llm_output.get("model_name")
            model_name = model_name or "unknown"

            token_usage = extract_token_usage(response)
            prompt_tokens = int(token_usage["input"])
            completion_tokens = int(token_usage["output"])
            tool_call_count = len(extract_tool_calls(response))

            elapsed_ms = 0.0
            if self._llm_started_at is not None:
                elapsed_ms = (time.monotonic() - self._llm_started_at) * 1000.0

            run_ctx.step_count += 1
            run_ctx.cost += estimate_cost(model_name, prompt_tokens, completion_tokens)
            run_ctx.energy_used += estimate_energy(model_name, prompt_tokens, completion_tokens)
            run_ctx.latency_used_ms += elapsed_ms
            run_ctx.tool_calls += tool_call_count

            if run_ctx.budget_max is not None:
                run_ctx.budget_remaining = run_ctx.budget_max - run_ctx.cost

            if self._pre_action == "allow":
                run_ctx.record(
                    action="allow",
                    reason="langchain_step",
                    model=model_name,
                    applied=True,
                    decision_mode=run_ctx.mode,
                )
            elif not self._pre_recorded:
                run_ctx.record(
                    action=self._pre_action,
                    reason=self._pre_reason,
                    model=self._pre_model or model_name,
                    applied=False,
                    decision_mode=run_ctx.mode,
                )

        except Exception as exc:
            self._handle_harness_error(exc)
        finally:
            self._llm_started_at = None
            self._pre_action = "allow"
            self._pre_reason = "allow"
            self._pre_model = None
            self._pre_recorded = False

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> Any:
        try:
            self._sync_state(kwargs)
            run_ctx = get_current_run()
            if run_ctx is None:
                return None
            if run_ctx.tool_calls_max is None:
                return None

            if run_ctx.tool_calls >= run_ctx.tool_calls_max:
                if run_ctx.mode == "observe":
                    run_ctx.record(
                        action="deny_tool",
                        reason="max_tool_calls_reached",
                        model=self.current_model,
                        applied=False,
                        decision_mode="observe",
                    )
                    return None
                if run_ctx.mode == "enforce":
                    run_ctx.record(
                        action="deny_tool",
                        reason="max_tool_calls_reached",
                        model=self.current_model,
                        applied=True,
                        decision_mode="enforce",
                    )
                    raise HarnessStopError(
                        "cascadeflow harness deny_tool: max tool calls reached",
                        reason="max_tool_calls_reached",
                    )

            return None
        except Exception as exc:
            self._handle_harness_error(exc)
            return None


@contextmanager
def get_harness_callback(*, fail_open: bool = True):
    """Context manager that yields a harness-aware LangChain callback handler."""
    callback = HarnessAwareCascadeFlowCallbackHandler(fail_open=fail_open)
    yield callback


__all__ = ["HarnessAwareCascadeFlowCallbackHandler", "get_harness_callback"]

