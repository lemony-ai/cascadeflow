"""Custom exceptions for CascadeFlow."""


class CascadeFlowError(Exception):
    """Base exception for all CascadeFlow errors."""
    pass


class ConfigError(CascadeFlowError):
    """Configuration error."""
    pass


class ProviderError(CascadeFlowError):
    """Provider-related error."""

    def __init__(self, message: str, provider: str, original_error: Exception = None):
        super().__init__(message)
        self.provider = provider
        self.original_error = original_error


class ModelError(CascadeFlowError):
    """Model execution error."""

    def __init__(self, message: str, model: str, provider: str = None):
        super().__init__(message)
        self.model = model
        self.provider = provider


class BudgetExceededError(CascadeFlowError):
    """Budget limit exceeded."""

    def __init__(self, message: str, current: float, limit: float, remaining: float = 0.0):
        super().__init__(message)
        self.current = current
        self.limit = limit
        self.remaining = remaining


class RateLimitError(CascadeFlowError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = 3600):
        super().__init__(message)
        self.retry_after = retry_after


class QualityThresholdError(CascadeFlowError):
    """Quality threshold not met."""

    def __init__(self, message: str, confidence: float, threshold: float):
        super().__init__(message)
        self.confidence = confidence
        self.threshold = threshold


class RoutingError(CascadeFlowError):
    """Routing decision error."""
    pass


class ValidationError(CascadeFlowError):
    """Validation error."""
    pass