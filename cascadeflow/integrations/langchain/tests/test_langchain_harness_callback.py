"""Tests for harness-aware LangChain callback integration."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from cascadeflow.harness import init, reset, run
from cascadeflow.integrations.langchain.harness_callback import (
    HarnessAwareCascadeFlowCallbackHandler,
)
from cascadeflow.integrations.langchain.harness_state import (
    apply_langgraph_state,
    extract_langgraph_state,
)
from cascadeflow.schema.exceptions import BudgetExceededError, HarnessStopError


@pytest.fixture(autouse=True)
def _reset_harness_state() -> None:
    reset()


def _llm_result(model_name: str, prompt_tokens: int, completion_tokens: int) -> LLMResult:
    generation = ChatGeneration(message=AIMessage(content="ok"), generation_info={})
    return LLMResult(
        generations=[[generation]],
        llm_output={
            "model_name": model_name,
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        },
    )


def test_harness_callback_updates_active_run_metrics() -> None:
    init(mode="observe", budget=1.0)
    handler = HarnessAwareCascadeFlowCallbackHandler()

    with run(budget=1.0) as ctx:
        handler.on_llm_start(
            serialized={},
            prompts=["hello"],
            invocation_params={"model": "gpt-4o-mini"},
        )
        handler.on_llm_end(_llm_result("gpt-4o-mini", 120, 80))

        assert ctx.step_count == 1
        assert ctx.cost > 0
        assert ctx.energy_used > 0
        assert ctx.budget_remaining is not None
        assert ctx.budget_remaining < 1.0
        assert ctx.last_action == "allow"
        assert ctx.model_used == "gpt-4o-mini"


def test_harness_callback_enforce_raises_when_budget_exhausted() -> None:
    init(mode="enforce", budget=0.1)
    handler = HarnessAwareCascadeFlowCallbackHandler(fail_open=False)

    with run(budget=0.1) as ctx:
        ctx.cost = 0.1
        ctx.budget_remaining = 0.0

        with pytest.raises(BudgetExceededError):
            handler.on_llm_start(
                serialized={},
                prompts=["hello"],
                invocation_params={"model": "gpt-4o-mini"},
            )

        trace = ctx.trace()
        assert trace
        assert trace[-1]["action"] == "stop"
        assert trace[-1]["reason"] == "budget_exceeded"
        assert trace[-1]["applied"] is True


def test_harness_callback_observe_records_non_applied_decisions() -> None:
    init(mode="observe", budget=1.0)
    handler = HarnessAwareCascadeFlowCallbackHandler()

    with run(budget=1.0) as ctx:
        ctx.cost = 0.9
        ctx.budget_remaining = 0.1

        handler.on_llm_start(
            serialized={},
            prompts=["hello"],
            invocation_params={"model": "gpt-4o", "tools": [{"name": "lookup"}]},
        )

        trace = ctx.trace()
        assert trace
        assert trace[-1]["action"] in {"switch_model", "deny_tool"}
        assert trace[-1]["applied"] is False
        assert trace[-1]["decision_mode"] == "observe"


def test_harness_callback_enforce_denies_tool_when_limit_reached() -> None:
    init(mode="enforce", max_tool_calls=0, budget=1.0)
    handler = HarnessAwareCascadeFlowCallbackHandler(fail_open=False)

    with run(max_tool_calls=0, budget=1.0) as ctx:
        with pytest.raises(HarnessStopError, match="max tool calls"):
            handler.on_tool_start(serialized={"name": "search"}, input_str="query")

        trace = ctx.trace()
        assert trace
        assert trace[-1]["action"] == "deny_tool"
        assert trace[-1]["applied"] is True
        assert trace[-1]["decision_mode"] == "enforce"


def test_extract_and_apply_langgraph_state() -> None:
    state = extract_langgraph_state(
        {
            "metadata": {
                "langgraph_state": {
                    "step": 4,
                    "tool_calls": 3,
                    "budget_remaining": 0.42,
                    "latency_ms": 130.0,
                    "energy": 77.0,
                    "model": "gpt-4o-mini",
                }
            }
        }
    )

    assert state["step_count"] == 4
    assert state["tool_calls"] == 3
    assert state["model_used"] == "gpt-4o-mini"

    init(mode="observe", budget=1.0)
    with run(budget=1.0) as ctx:
        apply_langgraph_state(ctx, state)
        assert ctx.step_count == 4
        assert ctx.tool_calls == 3
        assert ctx.budget_remaining == pytest.approx(0.42)
        assert ctx.latency_used_ms == pytest.approx(130.0)
        assert ctx.energy_used == pytest.approx(77.0)
        assert ctx.model_used == "gpt-4o-mini"

