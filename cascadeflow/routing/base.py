"""
Base router interface for all routing strategies.

This defines the contract between routers and the agent.
Routers decide HOW to execute a query before execution starts.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class RoutingStrategy(Enum):
    """
    How to execute a query.

    This tells the agent what execution path to take.
    """

    DIRECT_CHEAP = "direct_cheap"  # Route to cheapest model
    DIRECT_BEST = "direct_best"  # Route to best model
    CASCADE = "cascade"  # Use cascade system
    PARALLEL = "parallel"  # Call multiple models (future)


@dataclass
class RoutingDecision:
    """
    Decision made by router about query execution.

    This is what routers return to the agent.

    Attributes:
        strategy: How to execute (DIRECT_BEST, CASCADE, etc)
        reason: Human-readable explanation
        confidence: Confidence in this decision (0-1)
        metadata: Additional routing metadata
        model_name: Specific model to use (optional)
        max_cost: Budget constraint (optional)
        min_quality: Quality requirement (optional)
    """

    strategy: RoutingStrategy
    reason: str
    confidence: float
    metadata: dict[str, Any]

    # Optional constraints
    model_name: Optional[str] = None
    max_cost: Optional[float] = None
    min_quality: Optional[float] = None

    def __post_init__(self):
        """Validate decision parameters."""
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence must be 0-1, got {self.confidence}")

    def is_direct(self) -> bool:
        """Check if this is a direct routing decision."""
        return self.strategy in [RoutingStrategy.DIRECT_BEST, RoutingStrategy.DIRECT_CHEAP]

    def is_cascade(self) -> bool:
        """Check if this is a cascade routing decision."""
        return self.strategy == RoutingStrategy.CASCADE


class Router(ABC):
    """
    Abstract base class for all routers.

    Routers decide HOW to execute a query before execution starts.
    This is "pre-routing" - decisions made BEFORE calling models.

    Future routers:
    - PreRouter: Based on complexity (current implementation)
    - SemanticRouter: Based on semantic similarity to examples
    - DomainRouter: Based on detected domain (code, math, etc)
    - HybridRouter: Combine multiple routing strategies
    - LearnedRouter: ML-based routing decisions
    """

    @abstractmethod
    async def route(self, query: str, context: Optional[dict[str, Any]] = None) -> RoutingDecision:
        """
        Decide how to handle this query.

        Args:
            query: User query text
            context: Optional context (user tier, budget, complexity, etc)

        Returns:
            RoutingDecision with strategy and metadata
        """
        pass

    def get_stats(self) -> dict[str, Any]:
        """
        Get router statistics (optional override).

        Returns:
            Dictionary with routing statistics
        """
        return {}

    def reset_stats(self) -> None:
        """Reset router statistics (optional override)."""
        pass


class RouterChain:
    """
    Chain multiple routers together.

    Useful for combining different routing strategies.
    First router to make a decision wins.
    """

    def __init__(self, routers: list[Router]):
        """
        Initialize router chain.

        Args:
            routers: List of routers to chain
        """
        self.routers = routers

    async def route(self, query: str, context: Optional[dict[str, Any]] = None) -> RoutingDecision:
        """
        Route through chain of routers.

        Args:
            query: User query text
            context: Optional context

        Returns:
            First non-None routing decision
        """
        for router in self.routers:
            decision = await router.route(query, context)
            if decision is not None:
                return decision

        # Fallback: direct to best
        return RoutingDecision(
            strategy=RoutingStrategy.DIRECT_BEST,
            reason="No router made a decision, using fallback",
            confidence=0.5,
            metadata={"fallback": True},
        )


__all__ = [
    "Router",
    "RoutingStrategy",
    "RoutingDecision",
    "RouterChain",
]
