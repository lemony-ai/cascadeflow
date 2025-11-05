"""
Utility functions and helpers for cascadeflow.

This module provides:
- Logging and formatting utilities (helpers.py)
- Response caching (caching.py)
- Convenience presets for quick setup (presets.py)
"""

# Caching
from .caching import ResponseCache

# Helpers (was utils.py)
from .helpers import (
    calculate_cosine_similarity,
    estimate_tokens,
    format_cost,
    get_env_or_raise,
    parse_model_identifier,
    setup_logging,
    truncate_text,
)

# Presets (v0.2.0 - function-based presets)
from .presets import (
    auto_agent,
    get_balanced_agent,
    get_cost_optimized_agent,
    get_development_agent,
    get_quality_optimized_agent,
    get_speed_optimized_agent,
)

__all__ = [
    # Helpers
    "setup_logging",
    "format_cost",
    "estimate_tokens",
    "truncate_text",
    "calculate_cosine_similarity",
    "get_env_or_raise",
    "parse_model_identifier",
    # Caching
    "ResponseCache",
    # Presets (v0.2.0 - function-based)
    "get_cost_optimized_agent",
    "get_balanced_agent",
    "get_speed_optimized_agent",
    "get_quality_optimized_agent",
    "get_development_agent",
    "auto_agent",
]
