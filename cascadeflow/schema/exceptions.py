"""
Custom Exception Hierarchy for cascadeflow
==========================================

This module defines all custom exceptions used throughout cascadeflow.

Exception Hierarchy:
    cascadeflowError (base)
    ├── ConfigError
    ├── ProviderError
    ├── ModelError
    ├── BudgetExceededError
    ├── RateLimitError
    ├── QualityThresholdError
    ├── RoutingError
    └── ValidationError

Usage:
    >>> from cascadeflow import cascadeflowError, ProviderError
    >>>
    >>> try:
    ...     result = await agent.run(query)
    ... except ProviderError as e:
    ...     print(f"Provider failed: {e}")
    ... except cascadeflowError as e:
    ...     print(f"Cascade error: {e}")

See Also:
    - agent.py for main error handling patterns
    - providers.base for provider-specific errors
"""


class cascadeflowError(Exception):
    """Base exception for cascadeflow."""

    pass


class ConfigError(cascadeflowError):
    """Configuration error."""

    pass


class ProviderError(cascadeflowError):
    """Provider error."""

    def __init__(self, message: str, provider: str = None, original_error: Exception = None):
        super().__init__(message)
        self.provider = provider
        self.original_error = original_error


class ModelError(cascadeflowError):
    """Model execution error."""

    def __init__(self, message: str, model: str = None, provider: str = None):
        super().__init__(message)
        self.model = model
        self.provider = provider


class BudgetExceededError(cascadeflowError):
    """Budget limit exceeded."""

    def __init__(self, message: str, remaining: float = 0.0):
        super().__init__(message)
        self.remaining = remaining


class RateLimitError(cascadeflowError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = 3600):
        super().__init__(message)
        self.retry_after = retry_after


class QualityThresholdError(cascadeflowError):
    """Quality threshold not met."""

    pass


class RoutingError(cascadeflowError):
    """Routing error."""

    pass


class ValidationError(cascadeflowError):
    """Validation error."""

    pass


# ==================== EXPORTS ====================

__all__ = [
    "cascadeflowError",
    "ConfigError",
    "ProviderError",
    "ModelError",
    "BudgetExceededError",
    "RateLimitError",
    "QualityThresholdError",
    "RoutingError",
    "ValidationError",
]
