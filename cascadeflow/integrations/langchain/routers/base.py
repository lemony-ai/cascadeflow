"""Base router interface for all routing strategies.

Routers decide HOW to execute a query before execution starts.
This is "pre-routing" - decisions made BEFORE calling models.

Port from @cascadeflow/core
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional, TypedDict

from typing_extensions import NotRequired


class RoutingStrategy(str, Enum):
    """How to execute a query.

    This tells the agent what execution path to take.
    """

    DIRECT_CHEAP = "direct_cheap"  # Route to cheapest model
    DIRECT_BEST = "direct_best"  # Route to best model
    CASCADE = "cascade"  # Use cascade system
    PARALLEL = "parallel"  # Call multiple models in parallel (future)


class RoutingDecision(TypedDict):
    """Decision made by router about query execution.

    This is what routers return to the agent.
    """

    strategy: RoutingStrategy  # How to execute (DIRECT_BEST, CASCADE, etc)
    reason: str  # Human-readable explanation
    confidence: float  # Confidence in this decision (0-1)
    metadata: dict[str, Any]  # Additional routing metadata
    model_name: NotRequired[str]  # Specific model to use (optional)
    max_cost: NotRequired[float]  # Budget constraint (optional)
    min_quality: NotRequired[float]  # Quality requirement (optional)


class RoutingDecisionHelper:
    """Helper functions for RoutingDecision."""

    @staticmethod
    def is_direct(decision: RoutingDecision) -> bool:
        """Check if decision is direct routing."""
        return decision["strategy"] in (RoutingStrategy.DIRECT_BEST, RoutingStrategy.DIRECT_CHEAP)

    @staticmethod
    def is_cascade(decision: RoutingDecision) -> bool:
        """Check if decision is cascade routing."""
        return decision["strategy"] == RoutingStrategy.CASCADE

    @staticmethod
    def validate(decision: RoutingDecision) -> None:
        """Validate routing decision."""
        if not (0 <= decision["confidence"] <= 1):
            raise ValueError(f"Confidence must be 0-1, got {decision['confidence']}")

    @staticmethod
    def create(
        strategy: RoutingStrategy,
        reason: str,
        confidence: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RoutingDecision:
        """Create a routing decision."""
        decision: RoutingDecision = {
            "strategy": strategy,
            "reason": reason,
            "confidence": confidence,
            "metadata": metadata or {},
        }

        RoutingDecisionHelper.validate(decision)
        return decision


class Router(ABC):
    """Abstract base class for all routers.

    Routers decide HOW to execute a query before execution starts.

    Future routers:
    - PreRouter: Based on complexity (current implementation)
    - SemanticRouter: Based on semantic similarity to examples
    - DomainRouter: Based on detected domain (code, math, etc)
    - HybridRouter: Combine multiple routing strategies
    - LearnedRouter: ML-based routing decisions
    """

    @abstractmethod
    async def route(self, query: str, context: Optional[dict[str, Any]] = None) -> RoutingDecision:
        """Decide how to handle this query.

        Args:
            query: User query text
            context: Optional context (user tier, budget, complexity, etc)

        Returns:
            RoutingDecision with strategy and metadata
        """
        pass

    def get_stats(self) -> dict[str, Any]:
        """Get router statistics (optional override).

        Returns:
            Dictionary with routing statistics
        """
        return {}

    def reset_stats(self) -> None:
        """Reset router statistics (optional override)."""
        pass


class RouterChain:
    """Chain multiple routers together.

    Useful for combining different routing strategies.
    First router to make a decision wins.

    Example:
        >>> chain = RouterChain([
        ...     ToolRouter(),
        ...     TierRouter(),
        ...     PreRouter(),
        ... ])
        >>> decision = await chain.route('What is AI?')
    """

    def __init__(self, routers: list[Router]):
        """Initialize router chain.

        Args:
            routers: List of routers to chain
        """
        self.routers = routers

    async def route(self, query: str, context: Optional[dict[str, Any]] = None) -> RoutingDecision:
        """Route through chain of routers.

        Args:
            query: User query text
            context: Optional context

        Returns:
            First non-null routing decision
        """
        for router in self.routers:
            decision = await router.route(query, context)
            if decision:
                return decision

        # Fallback: direct to best
        return RoutingDecisionHelper.create(
            RoutingStrategy.DIRECT_BEST,
            "No router made a decision, using fallback",
            0.5,
            {"fallback": True},
        )
