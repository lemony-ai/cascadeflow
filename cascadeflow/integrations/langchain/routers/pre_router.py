"""Pre-execution router based on query complexity.

This router makes decisions BEFORE cascade execution starts,
routing queries to either cascade or direct execution based
on detected complexity level.

Routing Logic:
- TRIVIAL/SIMPLE/MODERATE → CASCADE (cost optimization)
- HARD/EXPERT → DIRECT_BEST (quality priority)

Port from @cascadeflow/core
"""

from typing import Any, Optional, TypedDict

from typing_extensions import NotRequired

from ..complexity import ComplexityDetector, QueryComplexity
from .base import (
    Router,
    RoutingDecision,
    RoutingDecisionHelper,
    RoutingStrategy,
)


class PreRouterConfig(TypedDict):
    """Configuration for PreRouter."""

    enable_cascade: NotRequired[bool]  # Enable cascade routing (default: True)
    complexity_detector: NotRequired[ComplexityDetector]  # Custom detector
    cascade_complexities: NotRequired[list[QueryComplexity]]  # Which to cascade
    verbose: NotRequired[bool]  # Enable verbose logging


class PreRouterStats(TypedDict):
    """Statistics tracked by PreRouter."""

    total_queries: int  # Total queries routed
    by_complexity: dict[str, int]  # Distribution by complexity
    by_strategy: dict[str, int]  # Distribution by strategy
    cascade_rate: str  # Cascade rate percentage
    direct_rate: str  # Direct rate percentage
    forced_direct: int  # Number of forced direct routes
    cascade_disabled_count: int  # Queries when cascade was disabled


class PreRouter(Router):
    """Complexity-based pre-execution router.

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

    Example:
        >>> router = PreRouter({
        ...     'enable_cascade': True,
        ...     'cascade_complexities': ['trivial', 'simple', 'moderate'],
        ... })
        >>> decision = await router.route('What is 2+2?')
        >>> print(decision['strategy'])  # 'cascade'
    """

    def __init__(self, config: Optional[PreRouterConfig] = None):
        """Initialize PreRouter.

        Args:
            config: Optional configuration dictionary
        """
        config = config or {}

        self.enable_cascade = config.get("enable_cascade", True)
        self.detector = config.get("complexity_detector") or ComplexityDetector()
        self.verbose = config.get("verbose", False)

        # Default: cascade for simple queries, direct for complex
        default_cascade_complexities: list[QueryComplexity] = [
            "trivial",
            "simple",
            "moderate",
        ]

        self.cascade_complexities = set(
            config.get("cascade_complexities") or default_cascade_complexities
        )

        # Initialize statistics
        self.stats = {
            "total_queries": 0,
            "by_complexity": {},
            "by_strategy": {},
            "forced_direct": 0,
            "cascade_disabled": 0,
        }

        if self.verbose:
            print("PreRouter initialized:")
            print(f"  Cascade enabled: {self.enable_cascade}")
            print(f'  Cascade complexities: {", ".join(self.cascade_complexities)}')
            direct_complexities = [
                c
                for c in ["trivial", "simple", "moderate", "hard", "expert"]
                if c not in self.cascade_complexities
            ]
            print(f'  Direct complexities: {", ".join(direct_complexities)}')

    async def route(self, query: str, context: Optional[dict[str, Any]] = None) -> RoutingDecision:
        """Route query based on complexity.

        Context keys (optional):
        - 'complexity': Override auto-detection (QueryComplexity string)
        - 'complexity_hint': String hint for complexity
        - 'force_direct': Force direct routing
        - 'user_tier': User tier (for future premium routing)
        - 'budget': Budget constraint (for future cost-aware routing)

        Args:
            query: User query text
            context: Optional context dict

        Returns:
            RoutingDecision with strategy and metadata

        Example:
            >>> # Auto-detect complexity
            >>> decision1 = await router.route('What is 2+2?')
            >>>
            >>> # Override complexity
            >>> decision2 = await router.route('Complex query', {
            ...     'complexity': 'expert'
            ... })
            >>>
            >>> # Force direct routing
            >>> decision3 = await router.route('Any query', {
            ...     'force_direct': True
            ... })
        """
        context = context or {}

        # Update stats
        self.stats["total_queries"] += 1

        # === STEP 1: Detect Complexity ===
        complexity: QueryComplexity
        complexity_confidence: float

        if "complexity" in context:
            # Pre-detected complexity passed in
            complexity = context["complexity"]
            complexity_confidence = context.get("complexity_confidence", 1.0)
        elif "complexity_hint" in context:
            # String hint provided
            hint = context["complexity_hint"].lower()
            if self._is_valid_complexity(hint):
                complexity = hint  # type: ignore
                complexity_confidence = 1.0
            else:
                # Invalid hint, auto-detect
                result = self.detector.detect(query)
                complexity = result["complexity"]
                complexity_confidence = result["confidence"]
        else:
            # Auto-detect complexity
            result = self.detector.detect(query)
            complexity = result["complexity"]
            complexity_confidence = result["confidence"]

        # Track complexity
        complexity_count = self.stats["by_complexity"].get(complexity, 0)
        self.stats["by_complexity"][complexity] = complexity_count + 1

        # === STEP 2: Make Routing Decision ===
        force_direct = context.get("force_direct")

        strategy: RoutingStrategy
        reason: str
        confidence: float

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
            reason = f"{complexity} query suitable for cascade optimization"
            confidence = complexity_confidence
        else:
            # Complex query → direct for quality
            strategy = RoutingStrategy.DIRECT_BEST
            reason = f"{complexity} query requires best model for quality"
            confidence = complexity_confidence

        # Track strategy
        strategy_count = self.stats["by_strategy"].get(strategy.value, 0)
        self.stats["by_strategy"][strategy.value] = strategy_count + 1

        # === STEP 3: Build Decision ===
        decision = RoutingDecisionHelper.create(
            strategy,
            reason,
            confidence,
            {
                "complexity": complexity,
                "complexity_confidence": complexity_confidence,
                "router": "pre",
                "router_type": "complexity_based",
                "force_direct": force_direct,
                "cascade_enabled": self.enable_cascade,
            },
        )

        if self.verbose:
            query_preview = query[:50] + "..." if len(query) > 50 else query
            print(
                f"[PreRouter] {query_preview} → {strategy.value}\n"
                f"           Complexity: {complexity} (conf: {complexity_confidence:.2f})\n"
                f"           Reason: {reason}"
            )

        return decision

    def get_stats(self) -> PreRouterStats:
        """Get routing statistics.

        Returns:
            Dictionary with routing stats including:
            - total_queries: Total queries routed
            - by_complexity: Distribution by complexity
            - by_strategy: Distribution by strategy
            - cascade_rate: % of queries using cascade
            - direct_rate: % of queries using direct

        Example:
            >>> stats = router.get_stats()
            >>> print(f"Cascade rate: {stats['cascade_rate']}")
            >>> print(f"Complexity distribution: {stats['by_complexity']}")
        """
        total = self.stats["total_queries"]
        if total == 0:
            return {
                "total_queries": 0,
                "by_complexity": {},
                "by_strategy": {},
                "cascade_rate": "0.0%",
                "direct_rate": "0.0%",
                "forced_direct": 0,
                "cascade_disabled_count": 0,
            }

        cascade_count = self.stats["by_strategy"].get(RoutingStrategy.CASCADE.value, 0)
        direct_count = sum(
            count
            for strategy, count in self.stats["by_strategy"].items()
            if strategy.startswith("direct")
        )

        return {
            "total_queries": total,  # type: ignore[typeddict-item]
            "by_complexity": self.stats["by_complexity"].copy(),
            "by_strategy": self.stats["by_strategy"].copy(),
            "cascade_rate": f"{(cascade_count / total * 100):.1f}%",
            "direct_rate": f"{(direct_count / total * 100):.1f}%",
            "forced_direct": self.stats["forced_direct"],  # type: ignore[typeddict-item]
            "cascade_disabled_count": self.stats["cascade_disabled"],  # type: ignore[typeddict-item]
        }

    def reset_stats(self) -> None:
        """Reset all routing statistics."""
        self.stats = {
            "total_queries": 0,
            "by_complexity": {},
            "by_strategy": {},
            "forced_direct": 0,
            "cascade_disabled": 0,
        }

    def print_stats(self) -> None:
        """Print formatted routing statistics."""
        stats = self.get_stats()

        if stats["total_queries"] == 0:
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
            print(f"  {complexity.ljust(12)}: {str(count).rjust(4)} ({f'{pct:.1f}'.rjust(5)}%)")
        print()
        print("BY STRATEGY:")
        for strategy, count in stats["by_strategy"].items():
            pct = count / stats["total_queries"] * 100
            print(f"  {strategy.ljust(15)}: {str(count).rjust(4)} ({f'{pct:.1f}'.rjust(5)}%)")
        print("=" * 60 + "\n")

    def _is_valid_complexity(self, s: str) -> bool:
        """Check if string is valid complexity."""
        return s in ["trivial", "simple", "moderate", "hard", "expert"]


def create_pre_router(config: Optional[PreRouterConfig] = None) -> PreRouter:
    """Create a PreRouter with configuration.

    Args:
        config: PreRouter configuration

    Returns:
        Configured PreRouter instance

    Example:
        >>> from cascadeflow.integrations.langchain import create_pre_router
        >>>
        >>> router = create_pre_router({
        ...     'enable_cascade': True,
        ...     'verbose': True,
        ... })
    """
    return PreRouter(config)
