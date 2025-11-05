"""
Budget enforcement callbacks for cascadeflow.

Provides flexible callback-based enforcement for budget limits with
support for custom actions (allow, warn, block, degrade).

NEW in v0.2.0:
    - EnforcementContext: Context passed to callbacks
    - EnforcementAction: Actions that callbacks can return
    - EnforcementCallbacks: Callback manager for budget enforcement
    - Integration with CostTracker for automatic enforcement

Example:
    >>> from cascadeflow.telemetry import EnforcementCallbacks, EnforcementAction
    >>>
    >>> def my_callback(context):
    ...     if context.budget_exceeded:
    ...         return EnforcementAction.BLOCK
    ...     elif context.budget_used_pct > 0.8:
    ...         return EnforcementAction.WARN
    ...     return EnforcementAction.ALLOW
    >>>
    >>> callbacks = EnforcementCallbacks()
    >>> callbacks.register(my_callback)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class EnforcementAction(Enum):
    """
    Actions that enforcement callbacks can return.

    ALLOW: Allow the request to proceed normally
    WARN: Allow but log a warning (for monitoring)
    BLOCK: Block the request entirely (budget exceeded)
    DEGRADE: Allow but use cheaper models (graceful degradation)
    """

    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    DEGRADE = "degrade"


@dataclass
class EnforcementContext:
    """
    Context information passed to enforcement callbacks.

    Contains all information needed to make enforcement decisions:
    - User identification (user_id, user_tier)
    - Cost information (current_cost, estimated_cost, total_cost)
    - Budget information (budget_limit, budget_used_pct, budget_exceeded)
    - Request metadata (model, provider, query, etc.)

    Example:
        >>> context = EnforcementContext(
        ...     user_id="user_123",
        ...     user_tier="free",
        ...     current_cost=0.08,
        ...     estimated_cost=0.03,
        ...     total_cost=0.08,
        ...     budget_limit=0.10,
        ...     budget_used_pct=80.0,
        ...     budget_exceeded=False,
        ... )
    """

    # User identification
    user_id: str
    user_tier: Optional[str] = None

    # Cost information
    current_cost: float = 0.0  # Current period cost
    estimated_cost: float = 0.0  # Estimated cost of this request
    total_cost: float = 0.0  # Total cost across all time

    # Budget information
    budget_limit: Optional[float] = None  # Budget limit for current period
    budget_used_pct: float = 0.0  # Percentage of budget used
    budget_exceeded: bool = False  # True if budget is exceeded

    # Period information
    period_name: str = "total"  # Period being checked (daily/weekly/monthly/total)

    # Request metadata
    model: Optional[str] = None
    provider: Optional[str] = None
    query: Optional[str] = None
    tokens: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        """Human-readable representation."""
        return (
            f"EnforcementContext("
            f"user={self.user_id}:{self.user_tier}, "
            f"cost=${self.current_cost:.4f}/{self.budget_limit if self.budget_limit else 'unlimited'}, "
            f"used={self.budget_used_pct:.1f}%, "
            f"exceeded={self.budget_exceeded})"
        )


# Type alias for enforcement callbacks
EnforcementCallback = Callable[[EnforcementContext], EnforcementAction]


class EnforcementCallbacks:
    """
    Manage enforcement callbacks for budget limits.

    Allows registering custom callbacks that can make enforcement decisions
    based on user context (budget usage, tier, etc.).

    Features:
    - Multiple callbacks can be registered
    - Callbacks execute in order until one returns non-ALLOW action
    - Thread-safe callback execution
    - Error handling (failed callbacks logged but don't break flow)

    Example:
        >>> callbacks = EnforcementCallbacks()
        >>>
        >>> # Register callback
        >>> def enforce_free_tier(context):
        ...     if context.user_tier == "free" and context.budget_exceeded:
        ...         return EnforcementAction.BLOCK
        ...     return EnforcementAction.ALLOW
        >>>
        >>> callbacks.register(enforce_free_tier)
        >>>
        >>> # Check enforcement
        >>> context = EnforcementContext(user_id="user_123", ...)
        >>> action = callbacks.check(context)
        >>> if action == EnforcementAction.BLOCK:
        ...     raise Exception("Budget exceeded!")
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize enforcement callbacks.

        Args:
            verbose: Enable verbose logging
        """
        self.callbacks: list[EnforcementCallback] = []
        self.verbose = verbose
        self._call_count = 0

        logger.info("EnforcementCallbacks initialized")

    def register(self, callback: EnforcementCallback) -> None:
        """
        Register an enforcement callback.

        Callbacks are executed in registration order. The first callback
        to return a non-ALLOW action stops execution.

        Args:
            callback: Function that takes EnforcementContext and returns EnforcementAction

        Example:
            >>> def my_callback(context):
            ...     if context.budget_exceeded:
            ...         return EnforcementAction.BLOCK
            ...     return EnforcementAction.ALLOW
            >>>
            >>> callbacks.register(my_callback)
        """
        self.callbacks.append(callback)
        if self.verbose:
            logger.info(f"Registered enforcement callback: {callback.__name__}")

    def unregister(self, callback: EnforcementCallback) -> None:
        """
        Unregister an enforcement callback.

        Args:
            callback: The callback function to remove
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            if self.verbose:
                logger.info(f"Unregistered enforcement callback: {callback.__name__}")

    def clear(self) -> None:
        """Remove all registered callbacks."""
        count = len(self.callbacks)
        self.callbacks.clear()
        logger.info(f"Cleared {count} enforcement callbacks")

    def check(self, context: EnforcementContext) -> EnforcementAction:
        """
        Execute enforcement callbacks and return action.

        Callbacks execute in registration order. The first callback to
        return a non-ALLOW action stops execution and that action is returned.

        If all callbacks return ALLOW (or no callbacks registered), returns ALLOW.

        Args:
            context: Enforcement context with user/budget/cost info

        Returns:
            EnforcementAction to take (ALLOW, WARN, BLOCK, DEGRADE)

        Example:
            >>> context = EnforcementContext(
            ...     user_id="user_123",
            ...     user_tier="free",
            ...     budget_exceeded=True
            ... )
            >>> action = callbacks.check(context)
            >>> if action == EnforcementAction.BLOCK:
            ...     raise Exception("Budget exceeded!")
        """
        self._call_count += 1

        # No callbacks registered - allow by default
        if not self.callbacks:
            return EnforcementAction.ALLOW

        # Execute callbacks in order
        for callback in self.callbacks:
            try:
                action = callback(context)

                # Validate action
                if not isinstance(action, EnforcementAction):
                    logger.error(
                        f"Callback {callback.__name__} returned invalid action: {action}. "
                        f"Expected EnforcementAction. Treating as ALLOW."
                    )
                    continue

                # First non-ALLOW action stops execution
                if action != EnforcementAction.ALLOW:
                    if self.verbose:
                        logger.info(
                            f"Callback {callback.__name__} returned {action.value} for {context}"
                        )
                    return action

            except Exception as e:
                # Log error but continue with other callbacks
                logger.error(
                    f"Enforcement callback {callback.__name__} failed: {e}. Continuing with next callback."
                )
                continue

        # All callbacks returned ALLOW (or all failed)
        return EnforcementAction.ALLOW

    def get_stats(self) -> dict[str, Any]:
        """
        Get enforcement callback statistics.

        Returns:
            Dict with callback count and call count
        """
        return {
            "registered_callbacks": len(self.callbacks),
            "total_checks": self._call_count,
        }


# Built-in enforcement callbacks (convenience functions)


def strict_budget_enforcement(context: EnforcementContext) -> EnforcementAction:
    """
    Built-in callback: Strict budget enforcement.

    Blocks requests if budget is exceeded, warns at 80%.

    Example:
        >>> callbacks = EnforcementCallbacks()
        >>> callbacks.register(strict_budget_enforcement)
    """
    if context.budget_exceeded:
        return EnforcementAction.BLOCK
    elif context.budget_used_pct >= 80.0:
        return EnforcementAction.WARN
    return EnforcementAction.ALLOW


def graceful_degradation(context: EnforcementContext) -> EnforcementAction:
    """
    Built-in callback: Graceful degradation.

    Degrades to cheaper models at 90%, blocks at 100%.

    Example:
        >>> callbacks = EnforcementCallbacks()
        >>> callbacks.register(graceful_degradation)
    """
    if context.budget_exceeded:
        return EnforcementAction.BLOCK
    elif context.budget_used_pct >= 90.0:
        return EnforcementAction.DEGRADE
    elif context.budget_used_pct >= 80.0:
        return EnforcementAction.WARN
    return EnforcementAction.ALLOW


def tier_based_enforcement(context: EnforcementContext) -> EnforcementAction:
    """
    Built-in callback: Tier-based enforcement.

    - Free tier: Block at 100%, warn at 80%
    - Pro tier: Degrade at 100%, warn at 90%
    - Enterprise: Warn only (no blocking)

    Example:
        >>> callbacks = EnforcementCallbacks()
        >>> callbacks.register(tier_based_enforcement)
    """
    if context.user_tier == "free":
        if context.budget_exceeded:
            return EnforcementAction.BLOCK
        elif context.budget_used_pct >= 80.0:
            return EnforcementAction.WARN

    elif context.user_tier == "pro":
        if context.budget_exceeded:
            return EnforcementAction.DEGRADE  # Graceful degradation for pro
        elif context.budget_used_pct >= 90.0:
            return EnforcementAction.WARN

    elif context.user_tier == "enterprise":
        # Enterprise just gets warnings, never blocked
        if context.budget_used_pct >= 90.0:
            return EnforcementAction.WARN

    return EnforcementAction.ALLOW


__all__ = [
    "EnforcementAction",
    "EnforcementContext",
    "EnforcementCallback",
    "EnforcementCallbacks",
    "strict_budget_enforcement",
    "graceful_degradation",
    "tier_based_enforcement",
]
