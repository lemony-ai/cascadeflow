"""
cascadeflow - Agent runtime intelligence layer.

In-process harness that optimizes cost, latency, quality, budget, compliance,
and energy across AI agent workflows. Works inside agent execution loops with
full state awareness -- not an external proxy.

Quick start:
    import cascadeflow
    cascadeflow.init(mode="observe")
    # All OpenAI/Anthropic SDK calls are now tracked and traced.

Key APIs:
    cascadeflow.init(mode)        -- activate harness (off | observe | enforce)
    cascadeflow.run(budget)       -- scoped run with budget/trace
    @cascadeflow.agent(budget)    -- policy metadata on agent functions
    session.summary()             -- structured metrics
    session.trace()               -- full decision audit trail

Integrations: LangChain, OpenAI Agents SDK, CrewAI, Google ADK, n8n, Vercel AI SDK
"""

__version__ = "1.0.0"
__author__ = "Lemony Inc."
__license__ = "MIT"

# ==================== LAZY BACKWARD-COMPAT ALIASES ====================
# Old import paths (e.g. ``from cascadeflow.exceptions import ...``) are
# supported via sys.modules aliases.  We use a lightweight proxy so that
# the target submodule is only imported on first attribute access, keeping
# ``import cascadeflow`` fast.

import sys
import types


class _LazyModule(types.ModuleType):
    """Module proxy that defers import until first attribute access."""

    def __init__(self, alias_name: str, real_name: str):
        super().__init__(alias_name)
        self.__real_name = real_name
        self.__loaded = False

    def _load(self):
        if not self.__loaded:
            import importlib

            real = importlib.import_module(self.__real_name)
            self.__dict__.update(real.__dict__)
            self.__loaded = True

    def __getattr__(self, name: str):
        self._load()
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(
                f"module {self.__name__!r} has no attribute {name!r}"
            ) from None


# Register backward-compat aliases (lazy — no import happens here).
_COMPAT_ALIASES = {
    "cascadeflow.exceptions": "cascadeflow.schema.exceptions",
    "cascadeflow.result": "cascadeflow.schema.result",
    "cascadeflow.config": "cascadeflow.schema.config",
    "cascadeflow.core.config": "cascadeflow.schema.config",
    "cascadeflow.execution": "cascadeflow.core.execution",
    "cascadeflow.speculative": "cascadeflow.core.cascade",
    "cascadeflow.cascade": "cascadeflow.core.cascade",
}
for _alias, _real in _COMPAT_ALIASES.items():
    sys.modules[_alias] = _LazyModule(_alias, _real)

# ==================== EAGER IMPORTS ====================
# Only the harness API is loaded eagerly — it uses only stdlib imports.

from .harness import (  # noqa: E402
    HarnessConfig,
    HarnessInitReport,
    HarnessRunContext,
    init,
    reset,
    run,
    agent as harness_agent,
    get_harness_config,
    get_current_run,
    get_harness_callback_manager,
    set_harness_callback_manager,
)

# ==================== LAZY IMPORTS (PEP 562) ====================
# Everything else is loaded on first access to keep ``import cascadeflow`` fast.

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Agent & result
    "CascadeAgent": (".agent", "CascadeAgent"),
    "CascadeResult": (".schema.result", "CascadeResult"),
    # Providers
    "BaseProvider": (".providers", "BaseProvider"),
    "ModelResponse": (".providers", "ModelResponse"),
    "PROVIDER_REGISTRY": (".providers", "PROVIDER_REGISTRY"),
    # Schema — config
    "ModelConfig": (".schema.config", "ModelConfig"),
    "CascadeConfig": (".schema.config", "CascadeConfig"),
    "UserTier": (".schema.config", "UserTier"),
    "WorkflowProfile": (".schema.config", "WorkflowProfile"),
    "LatencyProfile": (".schema.config", "LatencyProfile"),
    "OptimizationWeights": (".schema.config", "OptimizationWeights"),
    "DEFAULT_TIERS": (".schema.config", "DEFAULT_TIERS"),
    "EXAMPLE_WORKFLOWS": (".schema.config", "EXAMPLE_WORKFLOWS"),
    # Schema — domain config
    "DomainConfig": (".schema.domain_config", "DomainConfig"),
    "DomainValidationMethod": (".schema.domain_config", "DomainValidationMethod"),
    "BUILTIN_DOMAIN_CONFIGS": (".schema.domain_config", "BUILTIN_DOMAIN_CONFIGS"),
    "create_domain_config": (".schema.domain_config", "create_domain_config"),
    "get_builtin_domain_config": (".schema.domain_config", "get_builtin_domain_config"),
    "DOMAIN_CODE": (".schema.domain_config", "DOMAIN_CODE"),
    "DOMAIN_GENERAL": (".schema.domain_config", "DOMAIN_GENERAL"),
    "DOMAIN_DATA": (".schema.domain_config", "DOMAIN_DATA"),
    "DOMAIN_MEDICAL": (".schema.domain_config", "DOMAIN_MEDICAL"),
    "DOMAIN_LEGAL": (".schema.domain_config", "DOMAIN_LEGAL"),
    "DOMAIN_MATH": (".schema.domain_config", "DOMAIN_MATH"),
    "DOMAIN_STRUCTURED": (".schema.domain_config", "DOMAIN_STRUCTURED"),
    # Schema — model registry
    "ModelRegistry": (".schema.model_registry", "ModelRegistry"),
    "ModelRegistryEntry": (".schema.model_registry", "ModelRegistryEntry"),
    "get_model": (".schema.model_registry", "get_model"),
    "has_model": (".schema.model_registry", "has_model"),
    "get_default_registry": (".schema.model_registry", "get_default_registry"),
    # Schema — exceptions
    "cascadeflowError": (".schema.exceptions", "cascadeflowError"),
    "ConfigError": (".schema.exceptions", "ConfigError"),
    "ProviderError": (".schema.exceptions", "ProviderError"),
    "ModelError": (".schema.exceptions", "ModelError"),
    "BudgetExceededError": (".schema.exceptions", "BudgetExceededError"),
    "RateLimitError": (".schema.exceptions", "RateLimitError"),
    "QualityThresholdError": (".schema.exceptions", "QualityThresholdError"),
    "RoutingError": (".schema.exceptions", "RoutingError"),
    "ValidationError": (".schema.exceptions", "ValidationError"),
    # Core — cascade
    "WholeResponseCascade": (".core.cascade", "WholeResponseCascade"),
    "SpeculativeCascade": (".core.cascade", "SpeculativeCascade"),
    "SpeculativeResult": (".core.cascade", "SpeculativeResult"),
    # Core — execution
    "DomainDetector": (".core.execution", "DomainDetector"),
    "ExecutionPlan": (".core.execution", "ExecutionPlan"),
    "ExecutionStrategy": (".core.execution", "ExecutionStrategy"),
    "LatencyAwareExecutionPlanner": (".core.execution", "LatencyAwareExecutionPlanner"),
    "ModelScorer": (".core.execution", "ModelScorer"),
    # Core — batch
    "BatchConfig": (".core.batch_config", "BatchConfig"),
    "BatchStrategy": (".core.batch_config", "BatchStrategy"),
    "BatchResult": (".core.batch", "BatchResult"),
    "BatchProcessingError": (".core.batch", "BatchProcessingError"),
    # Quality
    "ComplexityDetector": (".quality.complexity", "ComplexityDetector"),
    "QueryComplexity": (".quality.complexity", "QueryComplexity"),
    "QualityConfig": (".quality", "QualityConfig"),
    "QualityValidator": (".quality", "QualityValidator"),
    "ValidationResult": (".quality", "ValidationResult"),
    "ComparativeValidator": (".quality", "ComparativeValidator"),
    "AdaptiveThreshold": (".quality", "AdaptiveThreshold"),
    # Streaming
    "StreamManager": (".streaming", "StreamManager"),
    "StreamEventType": (".streaming", "StreamEventType"),
    "StreamEvent": (".streaming", "StreamEvent"),
    # Interface
    "VisualIndicator": (".interface.visual_consumer", "VisualIndicator"),
    "TerminalVisualConsumer": (".interface.visual_consumer", "TerminalVisualConsumer"),
    "SilentConsumer": (".interface.visual_consumer", "SilentConsumer"),
    # Telemetry
    "CallbackManager": (".telemetry.callbacks", "CallbackManager"),
    "CallbackEvent": (".telemetry.callbacks", "CallbackEvent"),
    "CallbackData": (".telemetry.callbacks", "CallbackData"),
    # Utils
    "ResponseCache": (".utils", "ResponseCache"),
    "estimate_tokens": (".utils", "estimate_tokens"),
    "format_cost": (".utils", "format_cost"),
    "setup_logging": (".utils", "setup_logging"),
    # Presets
    "auto_agent": (".utils.presets", "auto_agent"),
    "get_balanced_agent": (".utils.presets", "get_balanced_agent"),
    "get_cost_optimized_agent": (".utils.presets", "get_cost_optimized_agent"),
    "get_development_agent": (".utils.presets", "get_development_agent"),
    "get_quality_optimized_agent": (".utils.presets", "get_quality_optimized_agent"),
    "get_speed_optimized_agent": (".utils.presets", "get_speed_optimized_agent"),
    # Profiles
    "TierConfig": (".profiles", "TierConfig"),
    "TierLevel": (".profiles", "TierLevel"),
    "TIER_PRESETS": (".profiles", "TIER_PRESETS"),
    "UserProfile": (".profiles", "UserProfile"),
    "UserProfileManager": (".profiles", "UserProfileManager"),
    # Rate limiting
    "RateLimiter": (".limits", "RateLimiter"),
    "RateLimitState": (".limits", "RateLimitState"),
    # Guardrails
    "ContentModerator": (".guardrails", "ContentModerator"),
    "ModerationResult": (".guardrails", "ModerationResult"),
    "PIIDetector": (".guardrails", "PIIDetector"),
    "PIIMatch": (".guardrails", "PIIMatch"),
    "GuardrailsManager": (".guardrails", "GuardrailsManager"),
    "GuardrailViolation": (".guardrails", "GuardrailViolation"),
    # Config loader
    "load_config": (".config_loader", "load_config"),
    "load_agent": (".config_loader", "load_agent"),
    "load_default_agent": (".config_loader", "load_default_agent"),
    "create_agent_from_config": (".config_loader", "create_agent_from_config"),
    "find_config": (".config_loader", "find_config"),
    "parse_model_config": (".config_loader", "parse_model_config"),
    "parse_domain_config": (".config_loader", "parse_domain_config"),
    "EXAMPLE_YAML_CONFIG": (".config_loader", "EXAMPLE_YAML_CONFIG"),
    "EXAMPLE_JSON_CONFIG": (".config_loader", "EXAMPLE_JSON_CONFIG"),
    # Resilience
    "CircuitBreaker": (".resilience", "CircuitBreaker"),
    "CircuitBreakerConfig": (".resilience", "CircuitBreakerConfig"),
    "CircuitBreakerRegistry": (".resilience", "CircuitBreakerRegistry"),
    "CircuitState": (".resilience", "CircuitState"),
    "get_circuit_breaker": (".resilience", "get_circuit_breaker"),
    # Dynamic config
    "ConfigManager": (".dynamic_config", "ConfigManager"),
    "ConfigChangeEvent": (".dynamic_config", "ConfigChangeEvent"),
    "ConfigSection": (".dynamic_config", "ConfigSection"),
    "ConfigWatcher": (".dynamic_config", "ConfigWatcher"),
    # Rules
    "RuleContext": (".rules", "RuleContext"),
    "RuleDecision": (".rules", "RuleDecision"),
    "RuleEngine": (".rules", "RuleEngine"),
    # Tool risk
    "ToolRiskLevel": (".routing", "ToolRiskLevel"),
    "ToolRiskClassification": (".routing", "ToolRiskClassification"),
    "ToolRiskClassifier": (".routing", "ToolRiskClassifier"),
    "get_tool_risk_routing": (".routing", "get_tool_risk_routing"),
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        import importlib

        module = importlib.import_module(module_path, __package__)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return list(__all__) + list(_LAZY_IMPORTS)


# ==================== EXPORTS ====================
# Reduced to essential public API symbols. All lazy-loaded symbols
# remain accessible via attribute access but are not star-exported.

__all__ = [
    # Version
    "__version__",
    # Harness API (primary surface)
    "init",
    "run",
    "reset",
    "HarnessConfig",
    "HarnessRunContext",
    "HarnessInitReport",
    "harness_agent",
    "get_harness_config",
    "get_current_run",
    # Agent & config
    "CascadeAgent",
    "ModelConfig",
    "CascadeConfig",
    "CascadeResult",
    # Providers
    "BaseProvider",
    "ModelResponse",
    "PROVIDER_REGISTRY",
    # Exceptions
    "cascadeflowError",
    "BudgetExceededError",
]
