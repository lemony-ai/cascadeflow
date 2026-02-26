"""LangGraph/LangChain state extraction helpers for harness integration."""

from __future__ import annotations

from typing import Any, Mapping, Optional


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_candidate_state(source: Any) -> Optional[Mapping[str, Any]]:
    """Extract a named state container from a mapping.

    Only returns state from explicitly named keys (langgraph_state, graph_state,
    state).  Returns None when no named key matches — avoids treating arbitrary
    kwargs as harness state.
    """
    if not isinstance(source, Mapping):
        return None

    for key in ("langgraph_state", "graph_state", "state"):
        candidate = source.get(key)
        if isinstance(candidate, Mapping):
            return candidate

    return None


def extract_langgraph_state(payload: Any) -> dict[str, Any]:
    """Extract normalized harness-relevant fields from LangGraph-style state payloads."""

    candidates: list[Mapping[str, Any]] = []
    root = _extract_candidate_state(payload)
    if root is not None:
        candidates.append(root)

    if isinstance(payload, Mapping):
        metadata = payload.get("metadata")
        if isinstance(metadata, Mapping):
            state_from_metadata = _extract_candidate_state(metadata)
            if state_from_metadata is not None:
                candidates.append(state_from_metadata)

        configurable = payload.get("configurable")
        if isinstance(configurable, Mapping):
            state_from_configurable = _extract_candidate_state(configurable)
            if state_from_configurable is not None:
                candidates.append(state_from_configurable)

    merged: dict[str, Any] = {}
    for source in candidates:
        if "agent_id" in source and isinstance(source.get("agent_id"), str):
            merged["agent_id"] = source["agent_id"]
        if "model" in source and isinstance(source.get("model"), str):
            merged["model_used"] = source["model"]
        if "model_used" in source and isinstance(source.get("model_used"), str):
            merged["model_used"] = source["model_used"]

        step_count = _as_int(source.get("step_count", source.get("step")))
        if step_count is not None:
            merged["step_count"] = step_count

        tool_calls = _as_int(source.get("tool_calls"))
        if tool_calls is not None:
            merged["tool_calls"] = tool_calls

        budget_remaining = _as_float(source.get("budget_remaining"))
        if budget_remaining is not None:
            merged["budget_remaining"] = budget_remaining

        latency_used_ms = _as_float(source.get("latency_used_ms", source.get("latency_ms")))
        if latency_used_ms is not None:
            merged["latency_used_ms"] = latency_used_ms

        energy_used = _as_float(source.get("energy_used", source.get("energy")))
        if energy_used is not None:
            merged["energy_used"] = energy_used

    return merged


def apply_langgraph_state(run_ctx: Any, state: Mapping[str, Any]) -> None:
    """Apply extracted state fields onto an active HarnessRunContext."""
    if run_ctx is None or not isinstance(state, Mapping):
        return

    step_count = _as_int(state.get("step_count"))
    if step_count is not None and step_count > getattr(run_ctx, "step_count", 0):
        run_ctx.step_count = step_count

    tool_calls = _as_int(state.get("tool_calls"))
    if tool_calls is not None and tool_calls > getattr(run_ctx, "tool_calls", 0):
        run_ctx.tool_calls = tool_calls

    latency_used_ms = _as_float(state.get("latency_used_ms"))
    if latency_used_ms is not None and latency_used_ms > getattr(run_ctx, "latency_used_ms", 0.0):
        run_ctx.latency_used_ms = latency_used_ms

    energy_used = _as_float(state.get("energy_used"))
    if energy_used is not None and energy_used > getattr(run_ctx, "energy_used", 0.0):
        run_ctx.energy_used = energy_used

    budget_remaining = _as_float(state.get("budget_remaining"))
    if budget_remaining is not None:
        run_ctx.budget_remaining = budget_remaining

    model_used = state.get("model_used")
    if isinstance(model_used, str) and model_used:
        run_ctx.model_used = model_used

