"""Shared harness pricing and energy profiles.

This module centralizes model-cost and energy-estimation defaults used by
harness integrations (OpenAI auto-instrumentation, OpenAI Agents SDK, CrewAI,
Google ADK).

A future pricing registry will consolidate with ``cascadeflow.pricing``
and LiteLLM live data.  Until then this module is the canonical source
for harness-level cost/energy estimation.
"""

from __future__ import annotations

import re as _re
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
DEFAULT_PRICING_USD_PER_M: Final[tuple[float, float]] = (2.50, 10.00)

# Deterministic proxy coefficients for energy tracking.
ENERGY_COEFFICIENTS: Final[dict[str, float]] = {
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


# ---------------------------------------------------------------------------
# Fuzzy model-name resolution
# ---------------------------------------------------------------------------

# Pre-compiled pattern for stripping version/preview/date suffixes.
# Matches: -preview, -preview-05-20, -20250120, -latest, -exp-0827, etc.
_VERSION_SUFFIX_RE = _re.compile(
    r"(-preview(?:-\d{2,4}-\d{2})?|-\d{8,}|-latest|-exp(?:-\d+)?|-it)$"
)

# Cache for resolved model → pricing key lookups.
_pricing_key_cache: dict[str, str | None] = {}


def _resolve_pricing_key(model: str) -> str | None:
    """Resolve a model name to a known pricing table key.

    Tries exact match first, then strips version/preview/date suffixes,
    then tries longest-prefix match against known model names.
    Returns ``None`` when no match is found (caller should use defaults).
    """
    if model in _pricing_key_cache:
        return _pricing_key_cache[model]

    # Exact match
    if model in PRICING_USD_PER_M:
        _pricing_key_cache[model] = model
        return model

    # Strip version suffixes and retry
    stripped = _VERSION_SUFFIX_RE.sub("", model)
    if stripped != model and stripped in PRICING_USD_PER_M:
        _pricing_key_cache[model] = stripped
        return stripped

    # Longest-prefix match (e.g. "gemini-2.5-flash-8b" → "gemini-2.5-flash")
    best: str | None = None
    best_len = 0
    for known in PRICING_USD_PER_M:
        if model.startswith(known) and len(known) > best_len:
            best = known
            best_len = len(known)
    if best is not None:
        _pricing_key_cache[model] = best
        return best

    _pricing_key_cache[model] = None
    return None


# ---------------------------------------------------------------------------
# Public estimation helpers
# ---------------------------------------------------------------------------


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost from token usage."""
    key = _resolve_pricing_key(model)
    in_price, out_price = (
        PRICING_USD_PER_M.get(key, DEFAULT_PRICING_USD_PER_M) if key else DEFAULT_PRICING_USD_PER_M
    )
    return (input_tokens / 1_000_000.0) * in_price + (output_tokens / 1_000_000.0) * out_price


def estimate_energy(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate deterministic proxy energy units."""
    key = _resolve_pricing_key(model)
    coeff = (
        ENERGY_COEFFICIENTS.get(key, DEFAULT_ENERGY_COEFFICIENT)
        if key
        else DEFAULT_ENERGY_COEFFICIENT
    )
    return coeff * (input_tokens + (output_tokens * ENERGY_OUTPUT_WEIGHT))


def model_total_price(model: str) -> float:
    """Return total (input + output) price per 1M tokens."""
    key = _resolve_pricing_key(model)
    in_price, out_price = (
        PRICING_USD_PER_M.get(key, DEFAULT_PRICING_USD_PER_M) if key else DEFAULT_PRICING_USD_PER_M
    )
    return in_price + out_price
