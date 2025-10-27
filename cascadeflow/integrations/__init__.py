"""
CascadeFlow integrations with external services.

Provides optional integrations with:
    - LiteLLM: Cost tracking and multi-provider support
    - OpenTelemetry: Observability and metrics export
    - Other third-party services

All integrations are optional and gracefully degrade if dependencies unavailable.
"""

# Try to import LiteLLM integration
try:
    from .litellm import (
        SUPPORTED_PROVIDERS,
        LiteLLMCostProvider,
        get_model_cost,
        calculate_cost,
        validate_provider,
    )

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    SUPPORTED_PROVIDERS = None
    LiteLLMCostProvider = None
    get_model_cost = None
    calculate_cost = None
    validate_provider = None

__all__ = []

if LITELLM_AVAILABLE:
    __all__.extend([
        "SUPPORTED_PROVIDERS",
        "LiteLLMCostProvider",
        "get_model_cost",
        "calculate_cost",
        "validate_provider",
    ])

# Integration capabilities
INTEGRATION_CAPABILITIES = {
    "litellm": LITELLM_AVAILABLE,
    "opentelemetry": False,  # To be implemented in Milestone 2.2
}


def get_integration_info():
    """
    Get information about available integrations.

    Returns:
        Dict with integration availability

    Example:
        >>> from cascadeflow.integrations import get_integration_info
        >>> info = get_integration_info()
        >>> if info['litellm']:
        ...     print("LiteLLM integration available")
    """
    return {
        "capabilities": INTEGRATION_CAPABILITIES,
        "litellm_available": LITELLM_AVAILABLE,
    }
