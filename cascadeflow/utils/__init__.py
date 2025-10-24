"""
Utility functions and helpers for CascadeFlow.

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

# Presets
from .presets import (
    PRESET_ANTHROPIC_ONLY,
    PRESET_BEST_OVERALL,
    PRESET_FREE_LOCAL,
    PRESET_OPENAI_ONLY,
    PRESET_ULTRA_CHEAP,
    PRESET_ULTRA_FAST,
    PRESETS,
    CascadePresets,
    PerformanceMode,
    QualityMode,
    create_preset,
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
    # Presets
    "CascadePresets",
    "PRESET_BEST_OVERALL",
    "PRESET_ULTRA_FAST",
    "PRESET_ULTRA_CHEAP",
    "PRESET_OPENAI_ONLY",
    "PRESET_ANTHROPIC_ONLY",
    "PRESET_FREE_LOCAL",
    "PRESETS",
    "create_preset",
    "QualityMode",
    "PerformanceMode",
]
