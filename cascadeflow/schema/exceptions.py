"""
Custom Exception Hierarchy for CascadeFlow
==========================================

This module defines all custom exceptions used throughout CascadeFlow.

Exception Hierarchy:
    CascadeFlowError (base)
    ├── ConfigError
    ├── ProviderError
    ├── ModelError
    ├── BudgetExceededError
    ├── RateLimitError
    ├── QualityThresholdError
    ├── RoutingError
    └── ValidationError

Usage:
    >>> from cascadeflow import CascadeFlowError, ProviderError
    >>>
    >>> try:
    ...     result = await agent.run(query)
    ... except ProviderError as e:
    ...     print(f"Provider failed: {e}")
    ... except CascadeFlowError as e:
    ...     print(f"Cascade error: {e}")

See Also:
    - agent.py for main error handling patterns
    - providers.base for provider-specific errors
"""


class CascadeFlowError(Exception):
    """Base exception for CascadeFlow."""

    pass


class ConfigError(CascadeFlowError):
    """Configuration error."""

    pass


class ProviderError(CascadeFlowError):
    """Provider error."""

    def __init__(self, message: str, provider: str = None, original_error: Exception = None):
        super().__init__(message)
        self.provider = provider
        self.original_error = original_error


class ModelError(CascadeFlowError):
    """Model execution error."""

    def __init__(self, message: str, model: str = None, provider: str = None):
        super().__init__(message)
        self.model = model
        self.provider = provider


class BudgetExceededError(CascadeFlowError):
    """Budget limit exceeded."""

    def __init__(self, message: str, remaining: float = 0.0):
        super().__init__(message)
        self.remaining = remaining


class RateLimitError(CascadeFlowError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = 3600):
        super().__init__(message)
        self.retry_after = retry_after


class QualityThresholdError(CascadeFlowError):
    """Quality threshold not met."""

    pass


class RoutingError(CascadeFlowError):
    """Routing error."""

    pass


class ValidationError(CascadeFlowError):
    """Validation error."""

    pass


# ==================== EXPORTS ====================

__all__ = [
    "CascadeFlowError",
    "ConfigError",
    "ProviderError",
    "ModelError",
    "BudgetExceededError",
    "RateLimitError",
    "QualityThresholdError",
    "RoutingError",
    "ValidationError",
]
