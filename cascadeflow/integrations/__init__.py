"""
cascadeflow integrations with external services.

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
        LiteLLMBudgetTracker,
        cascadeflowLiteLLMCallback,
        setup_litellm_callbacks,
        get_model_cost,
        calculate_cost,
        validate_provider,
        get_provider_info,
    )

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    SUPPORTED_PROVIDERS = None
    LiteLLMCostProvider = None
    LiteLLMBudgetTracker = None
    cascadeflowLiteLLMCallback = None
    setup_litellm_callbacks = None
    get_model_cost = None
    calculate_cost = None
    validate_provider = None
    get_provider_info = None

# Try to import OpenTelemetry integration
try:
    from .otel import (
        OpenTelemetryExporter,
        MetricDimensions,
        cascadeflowMetrics,
        create_exporter_from_env,
    )

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    OpenTelemetryExporter = None
    MetricDimensions = None
    cascadeflowMetrics = None
    create_exporter_from_env = None

# Try to import LangChain integration
try:
    from .langchain import (
        CascadeFlow,
        with_cascade,
        CascadeConfig,
        CascadeResult,
        CostMetadata,
        TokenUsage,
        calculate_quality,
        calculate_cost,
        calculate_savings,
        create_cost_metadata,
        extract_token_usage,
        MODEL_PRICING,
    )

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    CascadeFlow = None
    with_cascade = None
    CascadeConfig = None
    CascadeResult = None
    CostMetadata = None
    TokenUsage = None
    calculate_quality = None
    calculate_cost = None
    calculate_savings = None
    create_cost_metadata = None
    extract_token_usage = None
    MODEL_PRICING = None

__all__ = []

if LITELLM_AVAILABLE:
    __all__.extend(
        [
            "SUPPORTED_PROVIDERS",
            "LiteLLMCostProvider",
            "LiteLLMBudgetTracker",
            "cascadeflowLiteLLMCallback",
            "setup_litellm_callbacks",
            "get_model_cost",
            "calculate_cost",
            "validate_provider",
            "get_provider_info",
        ]
    )

if OPENTELEMETRY_AVAILABLE:
    __all__.extend(
        [
            "OpenTelemetryExporter",
            "MetricDimensions",
            "cascadeflowMetrics",
            "create_exporter_from_env",
        ]
    )

if LANGCHAIN_AVAILABLE:
    __all__.extend(
        [
            "CascadeFlow",
            "with_cascade",
            "CascadeConfig",
            "CascadeResult",
            "CostMetadata",
            "TokenUsage",
            "calculate_quality",
            "calculate_cost",
            "calculate_savings",
            "create_cost_metadata",
            "extract_token_usage",
            "MODEL_PRICING",
        ]
    )

# Integration capabilities
INTEGRATION_CAPABILITIES = {
    "litellm": LITELLM_AVAILABLE,
    "opentelemetry": OPENTELEMETRY_AVAILABLE,
    "langchain": LANGCHAIN_AVAILABLE,
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
        "opentelemetry_available": OPENTELEMETRY_AVAILABLE,
        "langchain_available": LANGCHAIN_AVAILABLE,
    }
