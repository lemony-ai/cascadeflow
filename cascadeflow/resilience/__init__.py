"""
Resilience patterns for CascadeFlow.

Provides production-grade resilience features:
- Circuit Breaker: Prevent cascading failures
- Health monitoring: Track provider health

Example:
    >>> from cascadeflow.resilience import CircuitBreaker, CircuitState
    >>>
    >>> # Create circuit breaker for a provider
    >>> breaker = CircuitBreaker(
    ...     failure_threshold=5,
    ...     recovery_timeout=30.0,
    ...     half_open_max_calls=3
    ... )
    >>>
    >>> # Check if provider is available
    >>> if breaker.can_execute():
    ...     try:
    ...         result = await provider.complete(...)
    ...         breaker.record_success()
    ...     except Exception as e:
    ...         breaker.record_failure(e)
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitState",
    "get_circuit_breaker",
]
