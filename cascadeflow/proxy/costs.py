"""Cost and usage utilities for proxy responses."""

from __future__ import annotations

from typing import Any

from cascadeflow.schema.model_registry import ModelRegistry

from .models import ProxyRoute, ProxyUsage


def _coerce_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def extract_usage(payload: Any) -> ProxyUsage | None:
    """Extract token usage from a provider response payload."""
    if not isinstance(payload, dict):
        return None

    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None

    input_tokens = _coerce_int(
        usage.get("prompt_tokens")
        if usage.get("prompt_tokens") is not None
        else usage.get("input_tokens")
    )
    output_tokens = _coerce_int(
        usage.get("completion_tokens")
        if usage.get("completion_tokens") is not None
        else usage.get("output_tokens")
    )
    total_tokens = usage.get("total_tokens")
    if total_tokens is None:
        total_tokens = input_tokens + output_tokens

    return ProxyUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=_coerce_int(total_tokens),
    )


def calculate_cost(
    model: str,
    usage: ProxyUsage | None,
    route: ProxyRoute,
    registry: ModelRegistry | None = None,
) -> float | None:
    """Calculate cost for a proxy response."""
    if usage is None:
        return None

    cost_per_1k = route.cost_per_1k_tokens
    if cost_per_1k is None:
        registry = registry or ModelRegistry()
        entry = registry.get_or_none(model)
        cost_per_1k = entry.cost if entry else None

    if cost_per_1k is None:
        return None

    return (usage.total_tokens / 1000.0) * cost_per_1k
