"""
Circuit Breaker Pattern for Provider Resilience.

The circuit breaker prevents cascading failures by temporarily blocking
requests to unhealthy providers, allowing them time to recover.

State Machine:
    CLOSED → (failures >= threshold) → OPEN
    OPEN → (recovery_timeout elapsed) → HALF_OPEN
    HALF_OPEN → (success) → CLOSED
    HALF_OPEN → (failure) → OPEN

Example:
    >>> breaker = CircuitBreaker(
    ...     failure_threshold=5,
    ...     recovery_timeout=30.0
    ... )
    >>>
    >>> async def call_provider():
    ...     if not breaker.can_execute():
    ...         raise CircuitOpenError("Provider circuit is open")
    ...     try:
    ...         result = await provider.complete(...)
    ...         breaker.record_success()
    ...         return result
    ...     except Exception as e:
    ...         breaker.record_failure(e)
    ...         raise
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests flow through
    OPEN = "open"  # Blocking requests, provider is unhealthy
    HALF_OPEN = "half_open"  # Testing if provider recovered


class CircuitOpenError(Exception):
    """Raised when circuit is open and requests are blocked."""

    def __init__(self, provider: str, time_until_retry: float):
        self.provider = provider
        self.time_until_retry = time_until_retry
        super().__init__(
            f"Circuit breaker open for {provider}. " f"Retry in {time_until_retry:.1f}s"
        )


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for circuit breaker behavior.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds before attempting recovery (HALF_OPEN)
        half_open_max_calls: Max test calls allowed in HALF_OPEN state
        success_threshold: Successes needed in HALF_OPEN to close circuit
        failure_window: Time window for counting failures (sliding window)
        excluded_exceptions: Exceptions that don't count as failures
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3
    success_threshold: int = 2
    failure_window: float = 60.0  # 1 minute sliding window
    excluded_exceptions: tuple = ()


@dataclass
class CircuitMetrics:
    """Track circuit breaker statistics."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Blocked by open circuit
    state_changes: list = field(default_factory=list)
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None

    def get_summary(self) -> dict[str, Any]:
        """Get human-readable summary."""
        success_rate = self.successful_calls / self.total_calls if self.total_calls > 0 else 0

        return {
            "total_calls": self.total_calls,
            "successful": self.successful_calls,
            "failed": self.failed_calls,
            "rejected": self.rejected_calls,
            "success_rate": f"{success_rate:.1%}",
            "state_changes": len(self.state_changes),
            "last_failure": self.last_failure_time,
            "last_success": self.last_success_time,
        }


class CircuitBreaker:
    """
    Circuit Breaker for provider resilience.

    Implements the circuit breaker pattern with three states:
    - CLOSED: Normal operation, requests flow through
    - OPEN: Provider is unhealthy, requests are blocked
    - HALF_OPEN: Testing if provider has recovered

    Thread-safe implementation using locks.

    Example:
        >>> breaker = CircuitBreaker(
        ...     name="openai",
        ...     failure_threshold=5,
        ...     recovery_timeout=30.0
        ... )
        >>>
        >>> # Simple usage
        >>> if breaker.can_execute():
        ...     try:
        ...         result = await call_api()
        ...         breaker.record_success()
        ...     except Exception as e:
        ...         breaker.record_failure(e)
        >>>
        >>> # Context manager usage
        >>> async with breaker.protect():
        ...     result = await call_api()
    """

    def __init__(
        self, name: str = "default", config: Optional[CircuitBreakerConfig] = None, **kwargs
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit (usually provider name)
            config: Configuration object
            **kwargs: Config overrides (failure_threshold, recovery_timeout, etc.)
        """
        self.name = name
        self.config = config or CircuitBreakerConfig(**kwargs)

        # State management
        self._state = CircuitState.CLOSED
        self._lock = threading.RLock()

        # Failure tracking (sliding window)
        self._failures: deque = deque()  # (timestamp, exception) pairs

        # Recovery tracking
        self._opened_at: Optional[float] = None
        self._half_open_calls: int = 0
        self._half_open_successes: int = 0

        # Metrics
        self.metrics = CircuitMetrics()

        # Callbacks
        self._on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None

        logger.debug(
            f"CircuitBreaker '{name}' initialized: "
            f"threshold={self.config.failure_threshold}, "
            f"recovery={self.config.recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state (may trigger state transition)."""
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is in half-open state (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    def can_execute(self) -> bool:
        """
        Check if a request can be executed.

        Returns:
            True if request can proceed, False if blocked
        """
        with self._lock:
            state = self.state  # Triggers state check

            if state == CircuitState.CLOSED:
                return True

            if state == CircuitState.OPEN:
                return False

            # HALF_OPEN: Allow limited test calls
            if state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.config.half_open_max_calls:
                    return True
                return False

            return False

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self.metrics.total_calls += 1
            self.metrics.successful_calls += 1
            self.metrics.last_success_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                self._half_open_calls += 1

                # Check if enough successes to close circuit
                if self._half_open_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                    logger.info(
                        f"CircuitBreaker '{self.name}': "
                        f"Recovered! Circuit CLOSED after "
                        f"{self._half_open_successes} successful test calls"
                    )

            # Clean up old failures in CLOSED state
            if self._state == CircuitState.CLOSED:
                self._cleanup_old_failures()

    def record_failure(self, exception: Optional[Exception] = None) -> None:
        """
        Record a failed call.

        Args:
            exception: The exception that caused the failure
        """
        with self._lock:
            # Check if exception should be excluded
            if exception and isinstance(exception, self.config.excluded_exceptions):
                logger.debug(
                    f"CircuitBreaker '{self.name}': "
                    f"Excluded exception {type(exception).__name__}"
                )
                return

            self.metrics.total_calls += 1
            self.metrics.failed_calls += 1
            self.metrics.last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN immediately opens circuit
                self._half_open_calls += 1
                self._transition_to(CircuitState.OPEN)
                logger.warning(
                    f"CircuitBreaker '{self.name}': " f"Recovery failed, circuit OPEN again"
                )
                return

            # Track failure with timestamp
            now = time.time()
            self._failures.append((now, exception))

            # Cleanup old failures outside window
            self._cleanup_old_failures()

            # Check if threshold exceeded
            if len(self._failures) >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.warning(
                    f"CircuitBreaker '{self.name}': "
                    f"Threshold exceeded ({len(self._failures)} failures), "
                    f"circuit OPEN. Recovery in {self.config.recovery_timeout}s"
                )

    def record_rejection(self) -> None:
        """Record a rejected call (blocked by open circuit)."""
        with self._lock:
            self.metrics.rejected_calls += 1

    def force_open(self) -> None:
        """Manually force circuit open (for maintenance/testing)."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            logger.info(f"CircuitBreaker '{self.name}': Manually forced OPEN")

    def force_close(self) -> None:
        """Manually force circuit closed (reset)."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._failures.clear()
            logger.info(f"CircuitBreaker '{self.name}': Manually forced CLOSED")

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures.clear()
            self._opened_at = None
            self._half_open_calls = 0
            self._half_open_successes = 0
            self.metrics = CircuitMetrics()
            logger.info(f"CircuitBreaker '{self.name}': Reset to initial state")

    def get_time_until_retry(self) -> Optional[float]:
        """
        Get time remaining until circuit transitions to HALF_OPEN.

        Returns:
            Seconds until retry, or None if not in OPEN state
        """
        with self._lock:
            if self._state != CircuitState.OPEN or self._opened_at is None:
                return None

            elapsed = time.time() - self._opened_at
            remaining = self.config.recovery_timeout - elapsed
            return max(0, remaining)

    def on_state_change(self, callback: Callable[[CircuitState, CircuitState], None]) -> None:
        """
        Register callback for state changes.

        Args:
            callback: Function called with (old_state, new_state)
        """
        self._on_state_change = callback

    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": len(self._failures),
                "failure_threshold": self.config.failure_threshold,
                **self.metrics.get_summary(),
            }

    # ========================================================================
    # CONTEXT MANAGER SUPPORT
    # ========================================================================

    class _ProtectContext:
        """Async context manager for protected execution."""

        def __init__(self, breaker: "CircuitBreaker"):
            self.breaker = breaker

        async def __aenter__(self):
            if not self.breaker.can_execute():
                self.breaker.record_rejection()
                time_until_retry = self.breaker.get_time_until_retry() or 0
                raise CircuitOpenError(self.breaker.name, time_until_retry)
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                self.breaker.record_success()
            else:
                self.breaker.record_failure(exc_val)
            return False  # Don't suppress exception

    def protect(self) -> _ProtectContext:
        """
        Context manager for protected execution.

        Automatically records success/failure.

        Example:
            >>> async with breaker.protect():
            ...     result = await provider.complete(...)
        """
        return self._ProtectContext(self)

    # ========================================================================
    # INTERNAL METHODS
    # ========================================================================

    def _check_state_transition(self) -> None:
        """Check if state should transition (called with lock held)."""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if self._opened_at is not None:
                elapsed = time.time() - self._opened_at
                if elapsed >= self.config.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    logger.info(
                        f"CircuitBreaker '{self.name}': "
                        f"Recovery timeout elapsed, entering HALF_OPEN state"
                    )

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state (called with lock held)."""
        if self._state == new_state:
            return

        old_state = self._state
        self._state = new_state

        # Record state change
        self.metrics.state_changes.append(
            {
                "from": old_state.value,
                "to": new_state.value,
                "timestamp": time.time(),
            }
        )

        # State-specific actions
        if new_state == CircuitState.OPEN:
            self._opened_at = time.time()
            self._half_open_calls = 0
            self._half_open_successes = 0

        elif new_state == CircuitState.CLOSED:
            self._opened_at = None
            self._failures.clear()
            self._half_open_calls = 0
            self._half_open_successes = 0

        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._half_open_successes = 0

        # Invoke callback
        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    def _cleanup_old_failures(self) -> None:
        """Remove failures outside the sliding window (called with lock held)."""
        cutoff = time.time() - self.config.failure_window
        while self._failures and self._failures[0][0] < cutoff:
            self._failures.popleft()

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name='{self.name}', state={self._state.value}, "
            f"failures={len(self._failures)}/{self.config.failure_threshold})"
        )


# ============================================================================
# CIRCUIT BREAKER REGISTRY (Per-Provider Tracking)
# ============================================================================


class CircuitBreakerRegistry:
    """
    Registry for managing per-provider circuit breakers.

    Provides centralized access to circuit breakers by provider name.

    Example:
        >>> registry = CircuitBreakerRegistry()
        >>>
        >>> # Get or create circuit breaker for a provider
        >>> openai_breaker = registry.get_or_create("openai")
        >>> groq_breaker = registry.get_or_create("groq")
        >>>
        >>> # Check all provider states
        >>> health = registry.get_health_status()
    """

    _instance: Optional["CircuitBreakerRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CircuitBreakerRegistry":
        """Singleton pattern for global registry."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._circuits = {}
                    cls._instance._default_config = CircuitBreakerConfig()
        return cls._instance

    def get_or_create(
        self, name: str, config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        Get existing or create new circuit breaker.

        Args:
            name: Provider/circuit name
            config: Optional custom configuration

        Returns:
            CircuitBreaker instance
        """
        with self._lock:
            if name not in self._circuits:
                self._circuits[name] = CircuitBreaker(
                    name=name, config=config or self._default_config
                )
                logger.debug(f"Created new circuit breaker for '{name}'")
            return self._circuits[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name, or None if not exists."""
        return self._circuits.get(name)

    def set_default_config(self, config: CircuitBreakerConfig) -> None:
        """Set default configuration for new circuit breakers."""
        self._default_config = config

    def get_health_status(self) -> dict[str, dict[str, Any]]:
        """
        Get health status of all registered circuits.

        Returns:
            Dict mapping provider name to health info
        """
        status = {}
        for name, breaker in self._circuits.items():
            status[name] = {
                "state": breaker.state.value,
                "healthy": breaker.is_closed,
                "failures": len(breaker._failures),
                "time_until_retry": breaker.get_time_until_retry(),
            }
        return status

    def get_available_providers(self) -> list[str]:
        """Get list of providers with closed circuits."""
        return [name for name, breaker in self._circuits.items() if breaker.can_execute()]

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._circuits.values():
            breaker.reset()
        logger.info(f"Reset all {len(self._circuits)} circuit breakers")

    def __len__(self) -> int:
        return len(self._circuits)

    def __iter__(self):
        return iter(self._circuits.items())


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================


def get_circuit_breaker(
    provider: str, config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """
    Get circuit breaker for a provider from global registry.

    This is the recommended way to get circuit breakers for providers.

    Args:
        provider: Provider name (e.g., "openai", "anthropic")
        config: Optional custom configuration

    Returns:
        CircuitBreaker instance

    Example:
        >>> breaker = get_circuit_breaker("openai")
        >>> if breaker.can_execute():
        ...     result = await openai_provider.complete(...)
    """
    registry = CircuitBreakerRegistry()
    return registry.get_or_create(provider, config)
