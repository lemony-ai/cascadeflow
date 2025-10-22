"""
Pre-execution router based on query complexity.

This router makes decisions BEFORE cascade execution starts,
routing queries to either cascade or direct execution based
on detected complexity level.

Routing Logic:
- TRIVIAL/SIMPLE/MODERATE → CASCADE (cost optimization)
- HARD/EXPERT → DIRECT_BEST (quality priority)
"""

import logging
from collections import defaultdict
from typing import Any, Optional

from cascadeflow.quality.complexity import ComplexityDetector, QueryComplexity

from .base import Router, RoutingDecision, RoutingStrategy

logger = logging.getLogger(__name__)


class PreRouter(Router):
    """
    Complexity-based pre-execution router.

    Makes routing decisions before cascade execution starts.
    Routes based on detected query complexity:
    - Simple queries → cascade for cost savings
    - Complex queries → direct to best model for quality

    Features:
    - Automatic complexity detection
    - Configurable complexity thresholds
    - Statistics tracking by complexity and strategy
    - Confidence scoring for decisions

    Future Enhancements:
    - User tier integration (premium → direct)
    - Budget constraints (low budget → cascade)
    - Historical performance learning
    - Domain-specific routing rules
    """

    def __init__(
        self,
        enable_cascade: bool = True,
        complexity_detector: Optional[ComplexityDetector] = None,
        cascade_complexities: Optional[list[QueryComplexity]] = None,
        verbose: bool = False,
    ):
        """
        Initialize pre-router.

        Args:
            enable_cascade: Enable cascade routing (if False, always direct)
            complexity_detector: Custom complexity detector
            cascade_complexities: Which complexities should use cascade
            verbose: Enable verbose logging
        """
        self.enable_cascade = enable_cascade
        self.detector = complexity_detector or ComplexityDetector()
        self.verbose = verbose

        # Default: cascade for simple queries, direct for complex
        self.cascade_complexities = cascade_complexities or [
            QueryComplexity.TRIVIAL,
            QueryComplexity.SIMPLE,
            QueryComplexity.MODERATE,
        ]

        # Statistics tracking
        self.stats = {
            "total_queries": 0,
            "by_complexity": defaultdict(int),
            "by_strategy": defaultdict(int),
            "forced_direct": 0,
            "cascade_disabled": 0,
        }

        logger.info(
            f"PreRouter initialized:\n"
            f"  Cascade enabled: {enable_cascade}\n"
            f"  Cascade complexities: {[c.value for c in self.cascade_complexities]}\n"
            f"  Direct complexities: {[c.value for c in QueryComplexity if c not in self.cascade_complexities]}"
        )

    async def route(self, query: str, context: Optional[dict[str, Any]] = None) -> RoutingDecision:
        """
        Route query based on complexity.

        Context keys (optional):
        - 'complexity': Override auto-detection (QueryComplexity enum)
        - 'complexity_hint': String hint for complexity
        - 'force_direct': Force direct routing
        - 'user_tier': User tier (for future premium routing)
        - 'budget': Budget constraint (for future cost-aware routing)

        Args:
            query: User query text
            context: Optional context dict

        Returns:
            RoutingDecision with strategy and metadata
        """
        context = context or {}

        # Update stats
        self.stats["total_queries"] += 1

        # === STEP 1: Detect Complexity ===
        if "complexity" in context:
            # Pre-detected complexity passed in
            complexity = context["complexity"]
            if isinstance(complexity, str):
                complexity = QueryComplexity(complexity.lower())
            complexity_confidence = context.get("complexity_confidence", 1.0)
        elif "complexity_hint" in context:
            # String hint provided
            try:
                complexity = QueryComplexity(context["complexity_hint"].lower())
                complexity_confidence = 1.0
            except ValueError:
                complexity, complexity_confidence = self.detector.detect(
                    query, return_metadata=False
                )
        else:
            # Auto-detect complexity
            complexity, complexity_confidence = self.detector.detect(query, return_metadata=False)

        # Track complexity
        self.stats["by_complexity"][complexity.value] += 1

        # === STEP 2: Make Routing Decision ===
        force_direct = context.get("force_direct", False)

        if force_direct:
            # Forced direct routing
            strategy = RoutingStrategy.DIRECT_BEST
            reason = "Forced direct routing (bypass cascade)"
            confidence = 1.0
            self.stats["forced_direct"] += 1

        elif not self.enable_cascade:
            # Cascade system disabled
            strategy = RoutingStrategy.DIRECT_BEST
            reason = "Cascade disabled, routing to best model"
            confidence = 1.0
            self.stats["cascade_disabled"] += 1

        elif complexity in self.cascade_complexities:
            # Simple query → cascade for cost optimization
            strategy = RoutingStrategy.CASCADE
            reason = f"{complexity.value} query suitable for cascade optimization"
            confidence = complexity_confidence

        else:
            # Complex query → direct for quality
            strategy = RoutingStrategy.DIRECT_BEST
            reason = f"{complexity.value} query requires best model for quality"
            confidence = complexity_confidence

        # Track strategy
        self.stats["by_strategy"][strategy.value] += 1

        # === STEP 3: Build Decision ===
        decision = RoutingDecision(
            strategy=strategy,
            reason=reason,
            confidence=confidence,
            metadata={
                "complexity": complexity.value,
                "complexity_confidence": complexity_confidence,
                "router": "pre",
                "router_type": "complexity_based",
                "force_direct": force_direct,
                "cascade_enabled": self.enable_cascade,
            },
        )

        if self.verbose:
            print(
                f"[PreRouter] {query[:50]}... → {strategy.value}\n"
                f"           Complexity: {complexity.value} (conf: {complexity_confidence:.2f})\n"
                f"           Reason: {reason}"
            )

        logger.debug(
            f"Routed query to {strategy.value}: "
            f"complexity={complexity.value}, confidence={complexity_confidence:.2f}"
        )

        return decision

    def get_stats(self) -> dict[str, Any]:
        """
        Get routing statistics.

        Returns:
            Dictionary with routing stats including:
            - total_queries: Total queries routed
            - by_complexity: Distribution by complexity
            - by_strategy: Distribution by strategy
            - cascade_rate: % of queries using cascade
            - direct_rate: % of queries using direct
        """
        total = self.stats["total_queries"]
        if total == 0:
            return {"total_queries": 0, "message": "No queries routed yet"}

        cascade_count = self.stats["by_strategy"].get("cascade", 0)
        direct_count = sum(
            count
            for strategy, count in self.stats["by_strategy"].items()
            if strategy.startswith("direct")
        )

        return {
            "total_queries": total,
            "by_complexity": dict(self.stats["by_complexity"]),
            "by_strategy": dict(self.stats["by_strategy"]),
            "cascade_rate": f"{cascade_count / total * 100:.1f}%",
            "direct_rate": f"{direct_count / total * 100:.1f}%",
            "forced_direct": self.stats["forced_direct"],
            "cascade_disabled_count": self.stats["cascade_disabled"],
        }

    def reset_stats(self) -> None:
        """Reset all routing statistics."""
        self.stats = {
            "total_queries": 0,
            "by_complexity": defaultdict(int),
            "by_strategy": defaultdict(int),
            "forced_direct": 0,
            "cascade_disabled": 0,
        }
        logger.info("PreRouter stats reset")

    def print_stats(self) -> None:
        """Print formatted routing statistics."""
        stats = self.get_stats()

        if stats.get("total_queries", 0) == 0:
            print("No routing statistics available")
            return

        print("\n" + "=" * 60)
        print("PRE-ROUTER STATISTICS")
        print("=" * 60)
        print(f"Total Queries Routed: {stats['total_queries']}")
        print(f"Cascade Rate:         {stats['cascade_rate']}")
        print(f"Direct Rate:          {stats['direct_rate']}")
        print(f"Forced Direct:        {stats['forced_direct']}")
        print()
        print("BY COMPLEXITY:")
        for complexity, count in stats["by_complexity"].items():
            pct = count / stats["total_queries"] * 100
            print(f"  {complexity:12s}: {count:4d} ({pct:5.1f}%)")
        print()
        print("BY STRATEGY:")
        for strategy, count in stats["by_strategy"].items():
            pct = count / stats["total_queries"] * 100
            print(f"  {strategy:15s}: {count:4d} ({pct:5.1f}%)")
        print("=" * 60 + "\n")


class ConditionalRouter(Router):
    """
    Router that routes based on custom conditions.

    Example:
        router = ConditionalRouter(
            conditions=[
                (lambda q, ctx: len(q) < 10, RoutingStrategy.DIRECT_CHEAP),
                (lambda q, ctx: 'urgent' in q.lower(), RoutingStrategy.DIRECT_BEST),
            ],
            default=RoutingStrategy.CASCADE
        )
    """

    def __init__(
        self,
        conditions: list[tuple[callable, RoutingStrategy]],
        default: RoutingStrategy = RoutingStrategy.CASCADE,
        verbose: bool = False,
    ):
        """
        Initialize conditional router.

        Args:
            conditions: List of (condition_fn, strategy) tuples
            default: Default strategy if no conditions match
            verbose: Enable verbose logging
        """
        self.conditions = conditions
        self.default = default
        self.verbose = verbose
        self.stats = defaultdict(int)

    async def route(self, query: str, context: Optional[dict[str, Any]] = None) -> RoutingDecision:
        """Route based on conditions."""
        context = context or {}

        for condition_fn, strategy in self.conditions:
            try:
                if condition_fn(query, context):
                    self.stats[strategy.value] += 1
                    return RoutingDecision(
                        strategy=strategy,
                        reason=f"Matched condition: {condition_fn.__name__}",
                        confidence=1.0,
                        metadata={"condition_matched": True},
                    )
            except Exception as e:
                logger.warning(f"Condition {condition_fn} failed: {e}")

        # Default
        self.stats[self.default.value] += 1
        return RoutingDecision(
            strategy=self.default,
            reason="No conditions matched, using default",
            confidence=0.8,
            metadata={"default": True},
        )

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return dict(self.stats)


__all__ = [
    "PreRouter",
    "ConditionalRouter",
]
