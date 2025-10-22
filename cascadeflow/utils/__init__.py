"""
Utility functions and helpers for CascadeFlow.

This module provides:
- Logging and formatting utilities (helpers.py)
- Response caching (caching.py)
- Convenience presets for quick setup (presets.py)
"""

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

# Caching
from .caching import ResponseCache

# Presets
from .presets import CascadePresets

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
    # Presets
    "CascadePresets",
]