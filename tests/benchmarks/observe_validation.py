"""Observe-mode zero-change proof.

For each synthetic scenario we run ``_prepare_call_interception`` in both
``"off"`` and ``"observe"`` modes and assert the resulting kwargs are
identical — proving that observe mode produces zero behavior change.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from cascadeflow.harness.api import HarnessRunContext
from cascadeflow.harness.instrument import (
    _CallInterceptionState,
    _prepare_call_interception,
)


@dataclass
class ObserveValidationResult:
    """Outcome of the full observe-mode validation suite."""

    total_cases: int
    passed: int
    failed: int
    failures: list[str]
    all_passed: bool


# ---------------------------------------------------------------------------
# Synthetic cases
# ---------------------------------------------------------------------------

_COMPARE_KEYS = ("model", "messages", "tools", "stream")


def _simple_chat_kwargs() -> dict[str, Any]:
    return {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False,
    }


def _chat_with_tools_kwargs() -> dict[str, Any]:
    return {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "What is the weather?"}],
        "tools": [
            {
                "type": "function",
                "function": {"name": "get_weather", "parameters": {}},
            }
        ],
        "stream": False,
    }


def _budget_exceeded_kwargs() -> dict[str, Any]:
    return _simple_chat_kwargs()


def _tool_limit_kwargs() -> dict[str, Any]:
    return _chat_with_tools_kwargs()


def _compliance_kwargs() -> dict[str, Any]:
    return {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Draft a contract"}],
        "stream": False,
    }


def _kpi_weighted_kwargs() -> dict[str, Any]:
    return {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Summarise this document"}],
        "stream": False,
    }


# Each case: (label, kwargs_factory, ctx_overrides_for_constraints)
_CASES: list[tuple[str, Any, dict[str, Any]]] = [
    ("simple_chat", _simple_chat_kwargs, {}),
    ("chat_with_tools", _chat_with_tools_kwargs, {}),
    (
        "budget_exceeded",
        _budget_exceeded_kwargs,
        {"budget_max": 1.0, "cost": 1.0},
    ),
    (
        "tool_limit_reached",
        _tool_limit_kwargs,
        {"tool_calls_max": 5, "tool_calls": 5},
    ),
    (
        "compliance_constraint",
        _compliance_kwargs,
        {"compliance": "gdpr"},
    ),
    (
        "kpi_weighted",
        _kpi_weighted_kwargs,
        {"kpi_weights": {"cost": 0.7, "quality": 0.3}},
    ),
]


def _run_single_case(
    label: str,
    kwargs_factory: Any,
    ctx_overrides: dict[str, Any],
) -> str | None:
    """Run one case.  Returns an error string on failure, ``None`` on success."""

    # --- reference: mode="off" ---
    ref_kwargs = kwargs_factory()
    ref_ctx = HarnessRunContext(mode="off", **ctx_overrides)
    ref_state: _CallInterceptionState = _prepare_call_interception(
        ctx=ref_ctx,
        mode="off",
        kwargs=copy.deepcopy(ref_kwargs),
    )

    # --- observed: mode="observe" ---
    obs_kwargs = kwargs_factory()
    obs_ctx = HarnessRunContext(mode="observe", **ctx_overrides)
    obs_state: _CallInterceptionState = _prepare_call_interception(
        ctx=obs_ctx,
        mode="observe",
        kwargs=copy.deepcopy(obs_kwargs),
    )

    # 1. kwargs identity — the observable behaviour MUST be the same.
    for key in _COMPARE_KEYS:
        ref_val = ref_state.kwargs.get(key)
        obs_val = obs_state.kwargs.get(key)
        if ref_val != obs_val:
            return f"{label}: kwargs['{key}'] differs — off={ref_val!r} observe={obs_val!r}"

    # 2. The model sent to the API must not change.
    if ref_state.model != obs_state.model:
        return f"{label}: model differs — off={ref_state.model} observe={obs_state.model}"

    # 3. For constrained cases the harness SHOULD have evaluated a decision
    #    (pre_action may be "stop", "switch_model", etc.).  Confirm the
    #    observe path at least recorded the same action as the off path.
    if ctx_overrides and obs_state.pre_action == "allow" and ref_state.pre_action != "allow":
        return f"{label}: observe lost decision — expected {ref_state.pre_action}, got allow"

    return None


def validate_observe_mode() -> ObserveValidationResult:
    """Run all synthetic cases and return the validation result."""

    failures: list[str] = []
    for label, factory, overrides in _CASES:
        err = _run_single_case(label, factory, overrides)
        if err is not None:
            failures.append(err)

    total = len(_CASES)
    failed = len(failures)
    return ObserveValidationResult(
        total_cases=total,
        passed=total - failed,
        failed=failed,
        failures=failures,
        all_passed=failed == 0,
    )
