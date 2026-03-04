"""Shared pricing and energy estimation for harness integrations.

Provides approximate USD-per-1M-token pricing and deterministic energy
coefficients used by CrewAI, OpenAI Agents, Google ADK, and future
integration modules.

A future pricing registry will consolidate with ``cascadeflow.pricing``
and LiteLLM live data.  Until then this module is the canonical source
for harness-level cost/energy estimation.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Pricing (USD per 1M tokens: input, output)
# ---------------------------------------------------------------------------

PRICING_USD_PER_M: dict[str, tuple[float, float]] = {
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
    # Anthropic
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-3.5": (1.00, 5.00),
    "claude-opus-4.5": (5.00, 25.00),
    # Google Gemini
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
}
DEFAULT_PRICING_USD_PER_M: tuple[float, float] = (2.50, 10.00)

# ---------------------------------------------------------------------------
# Energy coefficients (deterministic proxy for compute intensity)
# ---------------------------------------------------------------------------

ENERGY_COEFFICIENTS: dict[str, float] = {
    # OpenAI
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
    # Anthropic
    "claude-sonnet-4": 1.0,
    "claude-haiku-3.5": 0.3,
    "claude-opus-4.5": 1.8,
    # Google Gemini
    "gemini-2.5-flash": 0.3,
    "gemini-2.5-pro": 1.2,
    "gemini-2.0-flash": 0.25,
    "gemini-1.5-flash": 0.2,
    "gemini-1.5-pro": 1.0,
}
DEFAULT_ENERGY_COEFFICIENT: float = 1.0
ENERGY_OUTPUT_WEIGHT: float = 1.5


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD from model name and token counts."""
    in_price, out_price = PRICING_USD_PER_M.get(model, DEFAULT_PRICING_USD_PER_M)
    return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price


def estimate_energy(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate energy proxy from model name and token counts."""
    coeff = ENERGY_COEFFICIENTS.get(model, DEFAULT_ENERGY_COEFFICIENT)
    return coeff * (input_tokens + output_tokens * ENERGY_OUTPUT_WEIGHT)
