"""
Model degradation for graceful budget handling.

Provides mappings from expensive models to cheaper alternatives
for graceful degradation when approaching budget limits.

NEW in v0.2.0:
    - ModelDegradationMap: Define model downgrade paths
    - get_cheaper_model(): Get cheaper alternative for a model
    - DEFAULT_DEGRADATION_MAP: Pre-configured degradation paths

Example:
    >>> from cascadeflow.telemetry.degradation import get_cheaper_model
    >>>
    >>> # Get cheaper alternative
    >>> cheaper = get_cheaper_model("gpt-4")
    >>> print(cheaper)  # "gpt-4o-mini"
    >>>
    >>> # Custom degradation map
    >>> custom_map = {
    ...     "gpt-4": "gpt-3.5-turbo",
    ...     "claude-3-opus": "claude-3-haiku",
    ... }
    >>> cheaper = get_cheaper_model("gpt-4", degradation_map=custom_map)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default model degradation map
# Maps expensive models → cheaper alternatives
DEFAULT_DEGRADATION_MAP = {
    # OpenAI models
    "gpt-4": "gpt-4o-mini",  # GPT-4 → GPT-4o mini (much cheaper)
    "gpt-4-turbo": "gpt-4o-mini",
    "gpt-4o": "gpt-4o-mini",
    "gpt-4o-mini": "gpt-3.5-turbo",  # Already cheap, but can go cheaper
    "gpt-3.5-turbo": None,  # Already cheapest, no downgrade
    # Anthropic models
    "claude-3-opus": "claude-3-sonnet",
    "claude-3-5-sonnet": "claude-3-haiku",
    "claude-3-sonnet": "claude-3-haiku",
    "claude-3-haiku": None,  # Already cheapest
    # Groq models (all very cheap, no degradation needed)
    "llama-3.1-70b": "llama-3.1-8b",
    "llama-3.1-8b": None,
    "mixtral-8x7b": "llama-3.1-8b",
    # Deepseek models
    "deepseek-coder": "deepseek-coder-1.3b",
    "deepseek-coder-1.3b": None,
    # Together.ai models
    "together/llama-3-70b": "together/llama-3-8b",
    "together/llama-3-8b": None,
}


def get_cheaper_model(
    model: str, degradation_map: Optional[dict[str, Optional[str]]] = None
) -> Optional[str]:
    """
    Get cheaper alternative for a model.

    Args:
        model: Current model name
        degradation_map: Optional custom degradation map (uses DEFAULT_DEGRADATION_MAP if not provided)

    Returns:
        Cheaper model name, or None if no cheaper alternative exists

    Example:
        >>> get_cheaper_model("gpt-4")
        'gpt-4o-mini'
        >>>
        >>> get_cheaper_model("gpt-3.5-turbo")
        None  # Already cheapest
        >>>
        >>> # Custom map
        >>> custom_map = {"gpt-4": "gpt-3.5-turbo"}
        >>> get_cheaper_model("gpt-4", degradation_map=custom_map)
        'gpt-3.5-turbo'
    """
    # Use provided map or default
    map_to_use = degradation_map if degradation_map is not None else DEFAULT_DEGRADATION_MAP

    # Look up cheaper model
    cheaper = map_to_use.get(model)

    if cheaper is None and model in map_to_use:
        # Model is in map but has no cheaper alternative
        logger.warning(f"Model {model} is already the cheapest option, no degradation available")
        return None

    if cheaper is None:
        # Model not in map - try to find a generic fallback
        logger.warning(
            f"Model {model} not in degradation map, using generic fallback to gpt-3.5-turbo"
        )
        return "gpt-3.5-turbo"  # Safe generic fallback

    logger.info(f"Degrading model: {model} → {cheaper}")
    return cheaper


def get_degradation_chain(
    model: str, degradation_map: Optional[dict[str, Optional[str]]] = None
) -> list[str]:
    """
    Get full degradation chain for a model.

    Returns list of models from current to cheapest.

    Args:
        model: Starting model name
        degradation_map: Optional custom degradation map

    Returns:
        List of models in degradation order (most expensive first)

    Example:
        >>> get_degradation_chain("gpt-4")
        ['gpt-4', 'gpt-4o-mini', 'gpt-3.5-turbo']
        >>>
        >>> get_degradation_chain("claude-3-opus")
        ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku']
    """
    chain = [model]
    current = model

    # Follow degradation chain until we hit None or loop detection
    seen = {model}
    max_depth = 10  # Prevent infinite loops

    for _ in range(max_depth):
        cheaper = get_cheaper_model(current, degradation_map)
        if cheaper is None:
            break
        if cheaper in seen:
            logger.error(f"Degradation loop detected: {cheaper} already in chain")
            break

        chain.append(cheaper)
        seen.add(cheaper)
        current = cheaper

    return chain


def estimate_cost_savings(from_model: str, to_model: str) -> Optional[float]:
    """
    Estimate cost savings percentage when degrading between models.

    This is a rough estimate based on typical pricing.
    For accurate costs, use LiteLLM integration (Phase 2).

    Args:
        from_model: Original model
        to_model: Degraded model

    Returns:
        Estimated savings as decimal (0.9 = 90% cheaper), or None if unknown

    Example:
        >>> savings = estimate_cost_savings("gpt-4", "gpt-4o-mini")
        >>> print(f"{savings*100:.0f}% cheaper")
        90% cheaper
    """
    # Rough cost estimates (per 1K tokens, combined input+output)
    # These are approximations - use LiteLLM for accurate pricing
    rough_costs = {
        # OpenAI
        "gpt-4": 0.06,
        "gpt-4-turbo": 0.03,
        "gpt-4o": 0.015,
        "gpt-4o-mini": 0.0003,
        "gpt-3.5-turbo": 0.0015,
        # Anthropic
        "claude-3-opus": 0.075,
        "claude-3-5-sonnet": 0.015,
        "claude-3-sonnet": 0.015,
        "claude-3-haiku": 0.0025,
        # Groq (very cheap)
        "llama-3.1-70b": 0.0001,
        "llama-3.1-8b": 0.00005,
        "mixtral-8x7b": 0.00024,
        # Deepseek
        "deepseek-coder": 0.0014,
        "deepseek-coder-1.3b": 0.0001,
    }

    from_cost = rough_costs.get(from_model)
    to_cost = rough_costs.get(to_model)

    if from_cost is None or to_cost is None:
        logger.warning(f"Unknown costs for {from_model} or {to_model}, cannot estimate savings")
        return None

    if from_cost == 0:
        return 0.0

    savings = (from_cost - to_cost) / from_cost
    return max(0.0, savings)  # Ensure non-negative


__all__ = [
    "DEFAULT_DEGRADATION_MAP",
    "get_cheaper_model",
    "get_degradation_chain",
    "estimate_cost_savings",
]
