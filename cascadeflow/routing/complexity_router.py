"""
Complexity-Based Tool Router

Routes tool calls based on complexity analysis (NOT model capability filtering).
Uses ToolComplexityAnalyzer to decide between CASCADE and DIRECT strategies.

This is SEPARATE from the main ToolRouter (which filters by model capability).

Architecture:
    ToolRouter (main) → Filters by supports_tools
    ComplexityRouter (this) → Routes by complexity level

Usage:
    from cascadeflow.routing import ToolComplexityAnalyzer, ComplexityRouter

    analyzer = ToolComplexityAnalyzer()
    router = ComplexityRouter(analyzer=analyzer)

    strategy = router.route_tool_call(query, tools)
    # strategy.decision = CASCADE or DIRECT_LARGE
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .tool_complexity import ToolAnalysisResult, ToolComplexityAnalyzer, ToolComplexityLevel

logger = logging.getLogger(__name__)


class ToolRoutingDecision(Enum):
    """
    Two execution strategies for tool calls.

    Based on 5-cluster complexity mapping:
    - TRIVIAL/SIMPLE/MODERATE (clusters 1-3) → TOOL_CASCADE
    - HARD/EXPERT (clusters 4-5) → TOOL_DIRECT_LARGE
    """

    TOOL_CASCADE = "tool_cascade"  # Try small model first (clusters 1-3)
    TOOL_DIRECT_LARGE = "tool_direct_large"  # Skip to large model (clusters 4-5)


@dataclass
class ToolRoutingStrategy:
    """
    Complete routing strategy for a tool call.

    Contains decision, complexity analysis, cost estimates, and reasoning.
    Used by SmartCascade to execute appropriate strategy.
    """

    decision: ToolRoutingDecision
    complexity_level: ToolComplexityLevel
    analysis: ToolAnalysisResult
    model_recommendation: str
    use_cascade: bool
    reasoning: list[str] = field(default_factory=list)
    estimated_cost_usd: float = 0.0
    estimated_latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable summary."""
        return (
            f"ToolRoutingStrategy("
            f"decision={self.decision.value}, "
            f"complexity={self.complexity_level.value}, "
            f"use_cascade={self.use_cascade})"
        )


class ComplexityRouter:
    """
    Routes tool calls based on complexity analysis.

    Maps 5 complexity clusters to 2 execution strategies:
    - Clusters 1-3 (TRIVIAL/SIMPLE/MODERATE) → TOOL_CASCADE
    - Clusters 4-5 (HARD/EXPERT) → TOOL_DIRECT_LARGE

    This is DIFFERENT from the main ToolRouter which filters by model capability.

    Conservative Strategy:
    - 85% of tool calls use CASCADE (built-in fallback)
    - 15% pre-route to large model (only when very confident)
    - Expected savings: 74-76% on tool calls

    Complexity Reuse:
    - PRIMARY: Makes routing decisions
    - SECONDARY: Provides complexity for adaptive quality thresholds

    Example:
        >>> analyzer = ToolComplexityAnalyzer()
        >>> router = ComplexityRouter(analyzer=analyzer)
        >>> strategy = router.route_tool_call(
        ...     query="Analyze Q3 sales and forecast Q4",
        ...     tools=[analytics_tools]
        ... )
        >>> print(strategy.decision)  # TOOL_DIRECT_LARGE
        >>> print(strategy.complexity_level)  # HARD
    """

    def __init__(
        self,
        analyzer: Optional[ToolComplexityAnalyzer] = None,
        small_model: str = "llama-3.1-8b",
        large_model: str = "llama-3.1-70b",
        small_model_cost: float = 0.00006,  # per 1K tokens
        large_model_cost: float = 0.0006,  # per 1K tokens
        avg_tokens_per_request: int = 1000,
        verbose: bool = False,
    ):
        """
        Initialize complexity router.

        Args:
            analyzer: ToolComplexityAnalyzer instance (creates default if None)
            small_model: Name of small model for cascade
            large_model: Name of large model for direct routing
            small_model_cost: Cost per 1K tokens for small model
            large_model_cost: Cost per 1K tokens for large model
            avg_tokens_per_request: Average tokens per request (for cost estimates)
            verbose: Enable verbose logging
        """
        self.analyzer = analyzer or ToolComplexityAnalyzer()
        self.small_model = small_model
        self.large_model = large_model
        self.small_cost = small_model_cost
        self.large_cost = large_model_cost
        self.avg_tokens = avg_tokens_per_request
        self.verbose = verbose

        # Statistics tracking
        self.stats = {
            "total_routes": 0,
            "cascade_routes": 0,
            "direct_routes": 0,
            "safety_overrides": 0,
            "complexity_distribution": {
                ToolComplexityLevel.TRIVIAL: 0,
                ToolComplexityLevel.SIMPLE: 0,
                ToolComplexityLevel.MODERATE: 0,
                ToolComplexityLevel.HARD: 0,
                ToolComplexityLevel.EXPERT: 0,
            },
            "total_estimated_savings_usd": 0.0,
        }

        if self.verbose:
            logger.info(
                f"ComplexityRouter initialized: " f"small={small_model}, large={large_model}"
            )

    def route_tool_call(
        self,
        query: str,
        tools: list[dict[str, Any]],
        context: Optional[dict[str, Any]] = None,
        safety_critical: bool = False,
    ) -> ToolRoutingStrategy:
        """
        Route tool call based on complexity.

        Decision Logic:
        1. Safety-critical → Always TOOL_DIRECT_LARGE
        2. Analyze complexity → Get cluster (1-5)
        3. Clusters 1-3 (TRIVIAL/SIMPLE/MODERATE) → TOOL_CASCADE
        4. Clusters 4-5 (HARD/EXPERT) → TOOL_DIRECT_LARGE

        Args:
            query: User query string
            tools: Available tools (REQUIRED)
            context: Optional conversation context
            safety_critical: Force large model regardless of complexity

        Returns:
            ToolRoutingStrategy with decision and cost estimates

        Example:
            >>> strategy = router.route_tool_call(
            ...     query="What's the weather in Paris?",
            ...     tools=[weather_tool]
            ... )
            >>> strategy.decision  # TOOL_CASCADE
            >>> strategy.complexity_level  # TRIVIAL
            >>> strategy.use_cascade  # True
        """
        self.stats["total_routes"] += 1

        # Safety override
        if safety_critical:
            self.stats["safety_overrides"] += 1
            return self._safety_route()

        # Analyze complexity
        analysis = self.analyzer.analyze_tool_call(query, tools, context)

        # Update complexity distribution
        self.stats["complexity_distribution"][analysis.complexity_level] += 1

        # Map complexity to routing strategy
        strategy = self._decide_strategy(analysis)

        # Update statistics
        if strategy.decision == ToolRoutingDecision.TOOL_CASCADE:
            self.stats["cascade_routes"] += 1
        else:
            self.stats["direct_routes"] += 1

        # Track estimated savings
        if strategy.use_cascade:
            self.stats["total_estimated_savings_usd"] += self._estimate_cascade_savings(
                analysis.complexity_level
            )

        if self.verbose:
            self._log_routing_decision(query, strategy)

        return strategy

    def _decide_strategy(self, analysis: ToolAnalysisResult) -> ToolRoutingStrategy:
        """
        Map complexity level to routing decision.

        Clusters 1-3 (TRIVIAL/SIMPLE/MODERATE) → CASCADE
        Clusters 4-5 (HARD/EXPERT) → DIRECT_LARGE
        """
        level = analysis.complexity_level

        # Clusters 1-3: CASCADE (85% of queries)
        if level in [
            ToolComplexityLevel.TRIVIAL,
            ToolComplexityLevel.SIMPLE,
            ToolComplexityLevel.MODERATE,
        ]:
            decision = ToolRoutingDecision.TOOL_CASCADE
            use_cascade = True
            model = self.small_model

            reasoning = [
                f"Complexity: {level.value} (score: {analysis.score:.1f})",
                "Using cascade: try small model → quality check → escalate if needed",
                "Cost-efficient with safety fallback",
            ]

            # Add complexity-specific reasoning
            if level == ToolComplexityLevel.TRIVIAL:
                reasoning.append("Very low complexity - high confidence in small model")
            elif level == ToolComplexityLevel.SIMPLE:
                reasoning.append("Low complexity - small model should handle well")
            else:  # MODERATE
                reasoning.append("Moderate complexity - cascade provides good balance")

        # Clusters 4-5: DIRECT_LARGE (15% of queries)
        else:
            decision = ToolRoutingDecision.TOOL_DIRECT_LARGE
            use_cascade = False
            model = self.large_model

            reasoning = [
                f"Complexity: {level.value} (score: {analysis.score:.1f})",
                "Pre-routing to large model: complexity too high for small model",
                "Skipping cascade for optimal quality",
            ]

            # Add complexity-specific reasoning
            if level == ToolComplexityLevel.HARD:
                reasoning.append("High complexity - requires large model capabilities")
            else:  # EXPERT
                reasoning.append("Expert-level complexity - large model essential")

        return ToolRoutingStrategy(
            decision=decision,
            complexity_level=level,
            analysis=analysis,
            model_recommendation=model,
            use_cascade=use_cascade,
            reasoning=reasoning + analysis.reasoning,
            estimated_cost_usd=self._estimate_cost(decision, level),
            estimated_latency_ms=self._estimate_latency(decision),
            metadata={
                "complexity_score": analysis.score,
                "signals": analysis.signals,
                "indicator_scores": analysis.indicator_scores,
            },
        )

    def _safety_route(self) -> ToolRoutingStrategy:
        """
        Create strategy for safety-critical queries.

        Always routes to large model directly.
        """
        return ToolRoutingStrategy(
            decision=ToolRoutingDecision.TOOL_DIRECT_LARGE,
            complexity_level=ToolComplexityLevel.EXPERT,  # Treat as expert
            analysis=ToolAnalysisResult(
                complexity_level=ToolComplexityLevel.EXPERT,
                score=20.0,
                signals={"safety_critical": True},
                reasoning=["Safety-critical query - forced to large model"],
            ),
            model_recommendation=self.large_model,
            use_cascade=False,
            reasoning=[
                "SAFETY-CRITICAL: Forced routing to large model",
                "No cascade - quality prioritized over cost",
            ],
            estimated_cost_usd=self.large_cost * (self.avg_tokens / 1000),
            estimated_latency_ms=self._estimate_latency(ToolRoutingDecision.TOOL_DIRECT_LARGE),
            metadata={"safety_critical": True},
        )

    def _estimate_cost(self, decision: ToolRoutingDecision, level: ToolComplexityLevel) -> float:
        """
        Estimate cost in USD for this routing decision.

        Factors in:
        - Model costs
        - Cascade acceptance rates
        - Token usage
        """
        tokens_k = self.avg_tokens / 1000.0

        if decision == ToolRoutingDecision.TOOL_CASCADE:
            # Estimate cascade cost based on acceptance rate
            # Different acceptance rates by complexity
            acceptance_rates = {
                ToolComplexityLevel.TRIVIAL: 0.92,  # 92% accept draft
                ToolComplexityLevel.SIMPLE: 0.76,  # 76% accept draft
                ToolComplexityLevel.MODERATE: 0.47,  # 47% accept draft
            }

            acceptance = acceptance_rates.get(level, 0.70)

            # Cost = (small model always) + (large model if rejected)
            cost_small = self.small_cost * tokens_k
            cost_large_if_reject = self.large_cost * tokens_k * (1 - acceptance)

            return cost_small + cost_large_if_reject

        else:  # TOOL_DIRECT_LARGE
            # Direct to large model
            return self.large_cost * tokens_k

    def _estimate_latency(self, decision: ToolRoutingDecision) -> float:
        """
        Estimate latency in milliseconds.

        Rough estimates:
        - Small model: ~500ms
        - Large model: ~1000ms
        - Cascade (if rejected): ~1500ms
        """
        if decision == ToolRoutingDecision.TOOL_CASCADE:
            # Assume some cascade attempts need escalation
            return 750.0  # Average of accept (500ms) and escalate (1500ms)
        else:
            # Direct to large model
            return 1000.0

    def _estimate_cascade_savings(self, level: ToolComplexityLevel) -> float:
        """
        Estimate savings from using cascade vs always using large model.
        """
        # Cost if always used large model
        cost_large_only = self.large_cost * (self.avg_tokens / 1000.0)

        # Cost with cascade (estimated)
        cost_with_cascade = self._estimate_cost(ToolRoutingDecision.TOOL_CASCADE, level)

        return max(0, cost_large_only - cost_with_cascade)

    def _log_routing_decision(self, query: str, strategy: ToolRoutingStrategy):
        """Log routing decision for debugging."""
        logger.info(
            f"\n{'='*60}\n"
            f"Complexity-Based Routing Decision\n"
            f"{'='*60}\n"
            f"Query: {query[:80]}{'...' if len(query) > 80 else ''}\n"
            f"Complexity: {strategy.complexity_level.value} "
            f"(score: {strategy.analysis.score:.1f})\n"
            f"Decision: {strategy.decision.value}\n"
            f"Model: {strategy.model_recommendation}\n"
            f"Use Cascade: {strategy.use_cascade}\n"
            f"Est. Cost: ${strategy.estimated_cost_usd:.6f}\n"
            f"Est. Latency: {strategy.estimated_latency_ms:.0f}ms\n"
            f"Reasoning:\n" + "\n".join(f"  • {r}" for r in strategy.reasoning[:3]) + f"\n{'='*60}"
        )

    def get_stats(self) -> dict[str, Any]:
        """
        Get routing statistics.

        Returns comprehensive statistics including:
        - Total routes
        - Cascade vs direct distribution
        - Complexity distribution
        - Estimated savings
        """
        total = self.stats["total_routes"]

        if total == 0:
            return {"total_routes": 0, "message": "No routes processed yet"}

        # Calculate percentages
        cascade_pct = (self.stats["cascade_routes"] / total) * 100
        direct_pct = (self.stats["direct_routes"] / total) * 100

        # Complexity distribution percentages
        complexity_pct = {
            level.value: (count / total) * 100
            for level, count in self.stats["complexity_distribution"].items()
        }

        # Estimate overall savings percentage
        # Assume average request costs $0.0006 with large model
        avg_large_cost = 0.0006
        avg_savings = self.stats["total_estimated_savings_usd"] / total
        savings_pct = (avg_savings / avg_large_cost) * 100 if avg_large_cost > 0 else 0

        return {
            "total_routes": total,
            "cascade_routes": self.stats["cascade_routes"],
            "direct_routes": self.stats["direct_routes"],
            "safety_overrides": self.stats["safety_overrides"],
            "cascade_percentage": cascade_pct,
            "direct_percentage": direct_pct,
            "complexity_distribution": complexity_pct,
            "total_estimated_savings_usd": self.stats["total_estimated_savings_usd"],
            "avg_savings_per_request_usd": avg_savings,
            "estimated_savings_percentage": savings_pct,
            "expected_performance": {
                "target_cascade_rate": "85%",
                "actual_cascade_rate": f"{cascade_pct:.1f}%",
                "target_savings": "74-76%",
                "estimated_savings": f"{savings_pct:.1f}%",
            },
        }

    def reset_stats(self):
        """Reset statistics tracking."""
        self.stats = {
            "total_routes": 0,
            "cascade_routes": 0,
            "direct_routes": 0,
            "safety_overrides": 0,
            "complexity_distribution": {
                ToolComplexityLevel.TRIVIAL: 0,
                ToolComplexityLevel.SIMPLE: 0,
                ToolComplexityLevel.MODERATE: 0,
                ToolComplexityLevel.HARD: 0,
                ToolComplexityLevel.EXPERT: 0,
            },
            "total_estimated_savings_usd": 0.0,
        }

        if self.verbose:
            logger.info("ComplexityRouter statistics reset")

    def print_stats(self):
        """Print statistics in human-readable format."""
        stats = self.get_stats()

        if stats.get("message"):
            print(stats["message"])
            return

        print("\n" + "=" * 60)
        print("Complexity Router Statistics")
        print("=" * 60)
        print(f"Total Routes: {stats['total_routes']}")
        print(f"  • CASCADE: {stats['cascade_routes']} ({stats['cascade_percentage']:.1f}%)")
        print(f"  • DIRECT: {stats['direct_routes']} ({stats['direct_percentage']:.1f}%)")
        print(f"  • Safety Overrides: {stats['safety_overrides']}")

        print("\nComplexity Distribution:")
        for level, pct in stats["complexity_distribution"].items():
            if pct > 0:
                bar = "█" * int(pct / 2)
                print(f"  {level:10s}: {pct:5.1f}% {bar}")

        print("\nCost Savings:")
        print(f"  Total Saved: ${stats['total_estimated_savings_usd']:.4f}")
        print(f"  Avg Per Request: ${stats['avg_savings_per_request_usd']:.6f}")
        print(f"  Est. Savings Rate: {stats['estimated_savings_percentage']:.1f}%")

        print("\nPerformance vs Target:")
        perf = stats["expected_performance"]
        print(
            f"  Cascade Rate: {perf['actual_cascade_rate']} (target: {perf['target_cascade_rate']})"
        )
        print(f"  Savings: {perf['estimated_savings']} (target: {perf['target_savings']})")
        print("=" * 60 + "\n")


__all__ = ["ComplexityRouter", "ToolRoutingDecision", "ToolRoutingStrategy"]
