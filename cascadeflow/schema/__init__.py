"""
Data schemas and configuration for cascadeflow.

This module contains:
- Configuration dataclasses (ModelConfig, CascadeConfig, etc.)
- Domain configuration (DomainConfig, DomainValidationMethod)
- Model registry (ModelRegistry, ModelRegistryEntry)
- Result dataclasses (CascadeResult)
- Custom exceptions
"""

from .config import (
    DEFAULT_TIERS,
    EXAMPLE_WORKFLOWS,
    CascadeConfig,
    LatencyProfile,
    ModelConfig,
    OptimizationWeights,
    UserTier,
    WorkflowProfile,
)
from .domain_config import (
    BUILTIN_DOMAIN_CONFIGS,
    DomainConfig,
    DomainValidationMethod,
    create_domain_config,
    get_builtin_domain_config,
    # Domain string constants (avoid circular imports)
    DOMAIN_CODE,
    DOMAIN_DATA,
    DOMAIN_STRUCTURED,
    DOMAIN_RAG,
    DOMAIN_CONVERSATION,
    DOMAIN_TOOL,
    DOMAIN_CREATIVE,
    DOMAIN_SUMMARY,
    DOMAIN_TRANSLATION,
    DOMAIN_MATH,
    DOMAIN_SCIENCE,
    DOMAIN_MEDICAL,
    DOMAIN_LEGAL,
    DOMAIN_FINANCIAL,
    DOMAIN_GENERAL,
)
from .exceptions import (
    AuthenticationError,
    BudgetExceededError,
    cascadeflowError,
    ConfigError,
    ModelError,
    ProviderError,
    QualityThresholdError,
    RateLimitError,
    RoutingError,
    TimeoutError,
    ToolExecutionError,
    ValidationError,
)
from .model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    get_default_registry,
    get_model,
    has_model,
)
from .result import CascadeResult

__all__ = [
    # Configuration
    "ModelConfig",
    "CascadeConfig",
    "UserTier",
    "WorkflowProfile",
    "LatencyProfile",
    "OptimizationWeights",
    "DEFAULT_TIERS",
    "EXAMPLE_WORKFLOWS",
    # Domain Configuration
    "DomainConfig",
    "DomainValidationMethod",
    "BUILTIN_DOMAIN_CONFIGS",
    "create_domain_config",
    "get_builtin_domain_config",
    # Domain string constants
    "DOMAIN_CODE",
    "DOMAIN_DATA",
    "DOMAIN_STRUCTURED",
    "DOMAIN_RAG",
    "DOMAIN_CONVERSATION",
    "DOMAIN_TOOL",
    "DOMAIN_CREATIVE",
    "DOMAIN_SUMMARY",
    "DOMAIN_TRANSLATION",
    "DOMAIN_MATH",
    "DOMAIN_SCIENCE",
    "DOMAIN_MEDICAL",
    "DOMAIN_LEGAL",
    "DOMAIN_FINANCIAL",
    "DOMAIN_GENERAL",
    # Model Registry
    "ModelRegistry",
    "ModelRegistryEntry",
    "get_default_registry",
    "get_model",
    "has_model",
    # Exceptions
    "cascadeflowError",
    "ConfigError",
    "ProviderError",
    "AuthenticationError",
    "TimeoutError",
    "ModelError",
    "BudgetExceededError",
    "RateLimitError",
    "QualityThresholdError",
    "RoutingError",
    "ValidationError",
    "ToolExecutionError",
    # Results
    "CascadeResult",
]
