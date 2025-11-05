"""
Data schemas and configuration for cascadeflow.

This module contains:
- Configuration dataclasses (ModelConfig, CascadeConfig, etc.)
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
from .exceptions import (
    BudgetExceededError,
    cascadeflowError,
    ConfigError,
    ModelError,
    ProviderError,
    QualityThresholdError,
    RateLimitError,
    RoutingError,
    ValidationError,
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
    # Exceptions
    "cascadeflowError",
    "ConfigError",
    "ProviderError",
    "ModelError",
    "BudgetExceededError",
    "RateLimitError",
    "QualityThresholdError",
    "RoutingError",
    "ValidationError",
    # Results
    "CascadeResult",
]
