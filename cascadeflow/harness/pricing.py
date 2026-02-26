"""Shared harness pricing and energy profiles.

This module centralizes model-cost and energy-estimation defaults used by
harness integrations (OpenAI auto-instrumentation, OpenAI Agents SDK, CrewAI).
"""

from __future__ import annotations

from typing import Final

# USD per 1M tokens (input, output).
PRICING_USD_PER_M: Final[dict[str, tuple[float, float]]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.20, 0.80),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (1.10, 4.40),
    # Anthropic aliases used by CrewAI model names.
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-3.5": (1.00, 5.00),
    "claude-opus-4.5": (5.00, 25.00),
}
DEFAULT_PRICING_USD_PER_M: Final[tuple[float, float]] = (2.50, 10.00)

# Deterministic proxy coefficients for energy tracking.
ENERGY_COEFFICIENTS: Final[dict[str, float]] = {
    "gpt-4o": 1.0,
    "gpt-4o-mini": 0.3,
    "gpt-5": 1.2,
    "gpt-5-mini": 0.35,
    "gpt-4-turbo": 1.5,
    "gpt-4": 1.5,
    "gpt-3.5-turbo": 0.2,
    "o1": 2.0,
    "o1-mini": 0.8,
    "o3-mini": 0.5,
}
DEFAULT_ENERGY_COEFFICIENT: Final[float] = 1.0
ENERGY_OUTPUT_WEIGHT: Final[float] = 1.5

# Explicit pools keep provider/model-switching logic constrained even though the
# pricing table is shared across integrations.
OPENAI_MODEL_POOL: Final[tuple[str, ...]] = (
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-5",
    "gpt-5-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
    "o1",
    "o1-mini",
    "o3-mini",
)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token usage."""
    in_price, out_price = PRICING_USD_PER_M.get(model, DEFAULT_PRICING_USD_PER_M)
    return (input_tokens / 1_000_000.0) * in_price + (output_tokens / 1_000_000.0) * out_price


def estimate_energy(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate deterministic proxy energy units."""
    coefficient = ENERGY_COEFFICIENTS.get(model, DEFAULT_ENERGY_COEFFICIENT)
    return coefficient * (input_tokens + (output_tokens * ENERGY_OUTPUT_WEIGHT))


def model_total_price(model: str) -> float:
    """Return total (input + output) price per 1M tokens."""
    in_price, out_price = PRICING_USD_PER_M.get(model, DEFAULT_PRICING_USD_PER_M)
    return in_price + out_price

