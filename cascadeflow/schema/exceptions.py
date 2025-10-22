"""Custom exceptions for CascadeFlow."""


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