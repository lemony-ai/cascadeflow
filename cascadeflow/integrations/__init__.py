"""
cascadeflow integrations with external services.

Provides optional integrations with:
    - LiteLLM: Cost tracking and multi-provider support
    - OpenTelemetry: Observability and metrics export
    - LangChain: LangChain LLM wrapper with cascading
    - OpenAI Agents SDK: Model provider for OpenAI Agents
    - OpenClaw: Routing hints and gateway adapter
    - Paygentic: Usage reporting and billing
    - CrewAI: Harness integration for CrewAI workflows
    - Google ADK: Plugin for Google Agent Development Kit

All integrations are optional and raise ``ImportError`` with an install
hint when the required dependency is missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


class _MissingIntegration:
    """Proxy that raises ImportError with install hint on any use."""

    def __init__(self, name: str, install_hint: str):
        self._name = name
        self._install_hint = install_hint

    def _fail(self):
        raise ImportError(
            f"{self._name} requires additional dependencies. " f"Install with: {self._install_hint}"
        )

    def __call__(self, *args, **kwargs):
        self._fail()

    def __getattr__(self, name: str):
        self._fail()

    def __bool__(self):
        return False

    def __repr__(self):
        return f"<MissingIntegration {self._name!r}>"


# ═══════════════════════════════════════════════════
# LiteLLM
# ═══════════════════════════════════════════════════

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
    _litellm_missing = _MissingIntegration("LiteLLM", "pip install litellm")
    SUPPORTED_PROVIDERS = _litellm_missing
    LiteLLMCostProvider = _litellm_missing
    LiteLLMBudgetTracker = _litellm_missing
    cascadeflowLiteLLMCallback = _litellm_missing
    setup_litellm_callbacks = _litellm_missing
    get_model_cost = _litellm_missing
    calculate_cost = _litellm_missing
    validate_provider = _litellm_missing
    get_provider_info = _litellm_missing

# ═══════════════════════════════════════════════════
# OpenTelemetry
# ═══════════════════════════════════════════════════

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
    _otel_missing = _MissingIntegration(
        "OpenTelemetry", "pip install opentelemetry-api opentelemetry-sdk"
    )
    OpenTelemetryExporter = _otel_missing
    MetricDimensions = _otel_missing
    cascadeflowMetrics = _otel_missing
    create_exporter_from_env = _otel_missing

# ═══════════════════════════════════════════════════
# LangChain
# ═══════════════════════════════════════════════════

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
    _langchain_missing = _MissingIntegration("LangChain", "pip install cascadeflow[langchain]")
    CascadeFlow = _langchain_missing
    with_cascade = _langchain_missing
    CascadeConfig = _langchain_missing
    CascadeResult = _langchain_missing
    CostMetadata = _langchain_missing
    TokenUsage = _langchain_missing
    calculate_quality = _langchain_missing
    calculate_cost = _langchain_missing
    calculate_savings = _langchain_missing
    create_cost_metadata = _langchain_missing
    extract_token_usage = _langchain_missing
    MODEL_PRICING = _langchain_missing

# ═══════════════════════════════════════════════════
# OpenAI Agents SDK
# ═══════════════════════════════════════════════════

try:
    from .openai_agents import (
        OPENAI_AGENTS_SDK_AVAILABLE,
        CascadeFlowModelProvider,
        OpenAIAgentsIntegrationConfig,
        create_openai_agents_provider,
        is_openai_agents_sdk_available,
    )

    OPENAI_AGENTS_AVAILABLE = OPENAI_AGENTS_SDK_AVAILABLE
except ImportError:
    OPENAI_AGENTS_AVAILABLE = False
    OPENAI_AGENTS_SDK_AVAILABLE = False
    _agents_missing = _MissingIntegration(
        "OpenAI Agents SDK", "pip install cascadeflow[openai-agents]"
    )
    CascadeFlowModelProvider = _agents_missing
    OpenAIAgentsIntegrationConfig = _agents_missing
    create_openai_agents_provider = _agents_missing
    is_openai_agents_sdk_available = _agents_missing

# ═══════════════════════════════════════════════════
# OpenClaw
# ═══════════════════════════════════════════════════

try:
    from .openclaw import (
        OpenClawRouteHint,
        OPENCLAW_NATIVE_CATEGORIES,
        CATEGORY_TO_DOMAIN,
        extract_explicit_tags,
        classify_openclaw_frame,
        OpenClawRoutingDecision,
        build_routing_decision,
        OpenClawAdapter,
        OpenClawAdapterConfig,
        OpenClawGatewayAdapter,
        OpenClawOpenAIServer,
        OpenClawOpenAIConfig,
    )

    OPENCLAW_AVAILABLE = True
except ImportError:
    OPENCLAW_AVAILABLE = False
    _openclaw_missing = _MissingIntegration("OpenClaw", "pip install cascadeflow[openclaw]")
    OpenClawRouteHint = _openclaw_missing
    OPENCLAW_NATIVE_CATEGORIES = _openclaw_missing
    CATEGORY_TO_DOMAIN = _openclaw_missing
    extract_explicit_tags = _openclaw_missing
    classify_openclaw_frame = _openclaw_missing
    OpenClawRoutingDecision = _openclaw_missing
    build_routing_decision = _openclaw_missing
    OpenClawAdapter = _openclaw_missing
    OpenClawAdapterConfig = _openclaw_missing
    OpenClawGatewayAdapter = _openclaw_missing
    OpenClawOpenAIServer = _openclaw_missing
    OpenClawOpenAIConfig = _openclaw_missing

# ═══════════════════════════════════════════════════
# Paygentic
# ═══════════════════════════════════════════════════

try:
    from .paygentic import (
        DEFAULT_PAYGENTIC_LIVE_URL,
        DEFAULT_PAYGENTIC_SANDBOX_URL,
        PaygenticAPIError,
        PaygenticConfig,
        PaygenticClient,
        PaygenticUsageReporter,
        PaygenticProxyService,
    )

    PAYGENTIC_AVAILABLE = True
except ImportError:
    PAYGENTIC_AVAILABLE = False
    _paygentic_missing = _MissingIntegration("Paygentic", "pip install paygentic")
    DEFAULT_PAYGENTIC_LIVE_URL = _paygentic_missing
    DEFAULT_PAYGENTIC_SANDBOX_URL = _paygentic_missing
    PaygenticAPIError = _paygentic_missing
    PaygenticConfig = _paygentic_missing
    PaygenticClient = _paygentic_missing
    PaygenticUsageReporter = _paygentic_missing
    PaygenticProxyService = _paygentic_missing

# ═══════════════════════════════════════════════════
# CrewAI
# ═══════════════════════════════════════════════════

try:
    from .crewai import (
        CREWAI_AVAILABLE,
        CrewAIHarnessConfig,
        enable as crewai_enable,
        disable as crewai_disable,
        is_available as crewai_is_available,
        is_enabled as crewai_is_enabled,
        get_config as crewai_get_config,
    )
except ImportError:
    CREWAI_AVAILABLE = False
    _crewai_missing = _MissingIntegration("CrewAI", "pip install cascadeflow[crewai]")
    CrewAIHarnessConfig = _crewai_missing
    crewai_enable = _crewai_missing
    crewai_disable = _crewai_missing
    crewai_is_available = _crewai_missing
    crewai_is_enabled = _crewai_missing
    crewai_get_config = _crewai_missing

# ═══════════════════════════════════════════════════
# Google ADK
# ═══════════════════════════════════════════════════

try:
    from .google_adk import (
        GOOGLE_ADK_AVAILABLE,
        GoogleADKHarnessConfig,
        CascadeFlowADKPlugin,
        enable as google_adk_enable,
        disable as google_adk_disable,
        is_available as google_adk_is_available,
        is_enabled as google_adk_is_enabled,
        get_config as google_adk_get_config,
    )
except ImportError:
    GOOGLE_ADK_AVAILABLE = False
    _adk_missing = _MissingIntegration("Google ADK", "pip install cascadeflow[google-adk]")
    GoogleADKHarnessConfig = _adk_missing
    CascadeFlowADKPlugin = _adk_missing
    google_adk_enable = _adk_missing
    google_adk_disable = _adk_missing
    google_adk_is_available = _adk_missing
    google_adk_is_enabled = _adk_missing
    google_adk_get_config = _adk_missing


# ═══════════════════════════════════════════════════
# Exports & Capabilities
# ═══════════════════════════════════════════════════

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

if OPENCLAW_AVAILABLE:
    __all__.extend(
        [
            "OpenClawRouteHint",
            "OPENCLAW_NATIVE_CATEGORIES",
            "CATEGORY_TO_DOMAIN",
            "extract_explicit_tags",
            "classify_openclaw_frame",
            "OpenClawRoutingDecision",
            "build_routing_decision",
            "OpenClawAdapter",
            "OpenClawAdapterConfig",
            "OpenClawGatewayAdapter",
            "OpenClawOpenAIServer",
            "OpenClawOpenAIConfig",
        ]
    )

if OPENAI_AGENTS_AVAILABLE:
    __all__.extend(
        [
            "OPENAI_AGENTS_SDK_AVAILABLE",
            "CascadeFlowModelProvider",
            "OpenAIAgentsIntegrationConfig",
            "create_openai_agents_provider",
            "is_openai_agents_sdk_available",
        ]
    )

if PAYGENTIC_AVAILABLE:
    __all__.extend(
        [
            "DEFAULT_PAYGENTIC_LIVE_URL",
            "DEFAULT_PAYGENTIC_SANDBOX_URL",
            "PaygenticAPIError",
            "PaygenticConfig",
            "PaygenticClient",
            "PaygenticUsageReporter",
            "PaygenticProxyService",
        ]
    )

if CREWAI_AVAILABLE:
    __all__.extend(
        [
            "CREWAI_AVAILABLE",
            "CrewAIHarnessConfig",
            "crewai_enable",
            "crewai_disable",
            "crewai_is_available",
            "crewai_is_enabled",
            "crewai_get_config",
        ]
    )

if GOOGLE_ADK_AVAILABLE:
    __all__.extend(
        [
            "GOOGLE_ADK_AVAILABLE",
            "GoogleADKHarnessConfig",
            "CascadeFlowADKPlugin",
            "google_adk_enable",
            "google_adk_disable",
            "google_adk_is_available",
            "google_adk_is_enabled",
            "google_adk_get_config",
        ]
    )

# Integration capabilities
INTEGRATION_CAPABILITIES = {
    "litellm": LITELLM_AVAILABLE,
    "opentelemetry": OPENTELEMETRY_AVAILABLE,
    "langchain": LANGCHAIN_AVAILABLE,
    "openai_agents": OPENAI_AGENTS_AVAILABLE,
    "openclaw": OPENCLAW_AVAILABLE,
    "paygentic": PAYGENTIC_AVAILABLE,
    "crewai": CREWAI_AVAILABLE,
    "google_adk": GOOGLE_ADK_AVAILABLE,
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
        "openai_agents_available": OPENAI_AGENTS_AVAILABLE,
        "openclaw_available": OPENCLAW_AVAILABLE,
        "paygentic_available": PAYGENTIC_AVAILABLE,
        "crewai_available": CREWAI_AVAILABLE,
        "google_adk_available": GOOGLE_ADK_AVAILABLE,
    }
