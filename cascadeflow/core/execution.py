"""
Execution Planning & Domain Detection
====================================

This module implements the intelligence layer for execution planning.

Core Capabilities:
    1. Domain Detection: Identify query domains (code, math, legal, etc.)
    2. Model Scoring: Multi-factor scoring with domain/size/semantic boosts
    3. Strategy Selection: Choose optimal execution strategy
    4. Constraint Validation: Check latency, cost, quality requirements
    5. Semantic Routing: Use hints for better routing (if available)

Core Classes:
    - DomainDetector: Detect query domains from keywords
    - ModelScorer: Score models based on multiple factors
    - LatencyAwareExecutionPlanner: Plan execution with latency constraints
    - ExecutionStrategy: Enum of available strategies
    - ExecutionPlan: Complete execution plan with reasoning

Execution Strategies:
    - DIRECT_CHEAP: Use cheapest model directly
    - DIRECT_BEST: Use best quality model directly
    - DIRECT_SMART: Use smartest model for the domain
    - SPECULATIVE: Draft → Validate → Maybe verifier (cascade)
    - PARALLEL_RACE: Run multiple models in parallel

Usage:
    >>> planner = LatencyAwareExecutionPlanner()
    >>> plan = planner.plan(
    ...     query="Write a Python function",
    ...     models=[cheap, expensive],
    ...     complexity=QueryComplexity.MODERATE
    ... )
    >>> print(f"Strategy: {plan.strategy}")
    >>> print(f"Estimated cost: ${plan.estimated_cost:.6f}")

See Also:
    - core.cascade for speculative execution implementation
    - quality.complexity for complexity detection
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from cascadeflow.quality.complexity import QueryComplexity

from ..schema.config import ModelConfig, OptimizationWeights, UserTier, WorkflowProfile

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """Execution strategies for cascade."""

    DIRECT_CHEAP = "direct_cheap"
    DIRECT_BEST = "direct_best"
    DIRECT_SMART = "direct_smart"
    SPECULATIVE = "speculative"
    PARALLEL_RACE = "parallel_race"


@dataclass
class ExecutionPlan:
    """Execution plan for a query."""

    strategy: ExecutionStrategy
    primary_model: Optional[ModelConfig]
    drafter: Optional[ModelConfig]
    verifier: Optional[ModelConfig]
    race_models: Optional[list[ModelConfig]]
    estimated_cost: float
    estimated_latency_ms: float
    reasoning: str
    metadata: dict


class DomainDetector:
    """Detect query domains for specialized routing."""

    DOMAIN_KEYWORDS = {
        "code": [
            "python",
            "javascript",
            "java",
            "code",
            "function",
            "class",
            "bug",
            "error",
            "debug",
            "implement",
            "algorithm",
            "api",
            "syntax",
            "compile",
            "runtime",
            "programming",
            "script",
            "variable",
            "loop",
            "if",
            "else",
            "return",
            "import",
            "react",
            "node",
            "django",
            "flask",
            "typescript",
            "c++",
            "rust",
            "go",
            "kotlin",
            "swift",
            "git",
            "github",
        ],
        "math": [
            "equation",
            "derivative",
            "integral",
            "calculate",
            "solve",
            "algebra",
            "calculus",
            "geometry",
            "trigonometry",
            "matrix",
            "probability",
            "statistics",
            "mean",
            "median",
            "variance",
            "standard deviation",
            "regression",
            "correlation",
            "theorem",
            "proof",
            "formula",
            "calculate",
            "compute",
        ],
        "data": [
            "dataframe",
            "pandas",
            "sql",
            "query",
            "database",
            "table",
            "csv",
            "excel",
            "analysis",
            "visualization",
            "plot",
            "chart",
            "numpy",
            "aggregate",
            "group by",
            "join",
            "merge",
            "filter",
            "transform",
            "pivot",
            "reshape",
            "clean data",
        ],
        "writing": [
            "write",
            "essay",
            "article",
            "blog",
            "content",
            "draft",
            "edit",
            "revise",
            "proofread",
            "grammar",
            "style",
            "tone",
            "paragraph",
            "introduction",
            "conclusion",
            "thesis",
            "persuasive",
            "narrative",
            "descriptive",
            "summary",
        ],
        "legal": [
            "contract",
            "agreement",
            "legal",
            "law",
            "clause",
            "terms",
            "liability",
            "compliance",
            "regulation",
            "statute",
            "court",
            "litigation",
            "plaintiff",
            "defendant",
            "jurisdiction",
        ],
        "medical": [
            "medical",
            "health",
            "disease",
            "symptom",
            "diagnosis",
            "treatment",
            "medication",
            "doctor",
            "patient",
            "clinical",
            "therapy",
            "prescription",
            "anatomy",
            "physiology",
        ],
        "finance": [
            "investment",
            "stock",
            "portfolio",
            "trading",
            "financial",
            "market",
            "equity",
            "bond",
            "dividend",
            "roi",
            "revenue",
            "profit",
            "balance sheet",
            "income statement",
            "valuation",
        ],
    }

    def detect(self, query: str) -> list[str]:
        """Detect domains present in query."""
        query_lower = query.lower()
        detected = []

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in query_lower)
            if matches > 0:
                detected.append(domain)
                logger.debug(f"Detected domain '{domain}': {matches} keywords")

        if not detected:
            detected = ["general"]

        return detected


class ModelScorer:
    """Score models using multi-factor optimization with domain/size/semantic boosts."""

    def __init__(self):
        self.domain_detector = DomainDetector()

    def score_models(
        self,
        models: list[ModelConfig],
        query: str,
        complexity: QueryComplexity,
        optimization: OptimizationWeights,
        query_domains: Optional[list[str]] = None,
        semantic_hints: Optional[dict[str, float]] = None,
    ) -> list[tuple[ModelConfig, float, dict]]:
        """
        Score all models for the query.

        Args:
            models: Available models
            query: User query
            complexity: Detected complexity
            optimization: Optimization weights
            query_domains: Detected domains (auto-detected if None)
            semantic_hints: Semantic similarity scores {model_name: similarity}
        """
        if query_domains is None:
            query_domains = self.domain_detector.detect(query)

        logger.debug(f"Query domains: {query_domains}")
        if semantic_hints:
            logger.debug(f"Semantic hints available for {len(semantic_hints)} models")

        scored = []

        for model in models:
            # Base multi-factor score
            cost_norm = self._normalize_cost(model.cost, models)
            speed_norm = self._normalize_speed(model.speed_ms, models)
            quality_norm = 1.0 - self._normalize_quality(model.quality_score, models)

            base_score = (
                optimization.cost * cost_norm
                + optimization.speed * speed_norm
                + optimization.quality * quality_norm
            )

            # Domain boost (2.0x if matches)
            domain_boost = 1.0
            if any(d in model.domains for d in query_domains):
                domain_boost = 2.0
                logger.debug(f"  {model.name}: DOMAIN MATCH → 2.0x boost")

            # Size boost (1.5x for small models on simple queries)
            size_boost = 1.0
            is_small = model.quality_score < 0.7
            is_simple = complexity in [QueryComplexity.TRIVIAL, QueryComplexity.SIMPLE]
            if is_small and is_simple:
                size_boost = 1.5
                logger.debug(f"  {model.name}: SMALL+SIMPLE → 1.5x boost")

            # Semantic boost (1.5x-2.0x based on similarity)
            semantic_boost = 1.0
            semantic_similarity = 0.0
            if semantic_hints and model.name in semantic_hints:
                semantic_similarity = semantic_hints[model.name]
                # Scale similarity (0.3-1.0) to boost (1.0-2.0)
                if semantic_similarity >= 0.7:
                    semantic_boost = 1.8
                elif semantic_similarity >= 0.5:
                    semantic_boost = 1.5
                elif semantic_similarity >= 0.3:
                    semantic_boost = 1.2

                if semantic_boost > 1.0:
                    logger.debug(
                        f"  {model.name}: SEMANTIC MATCH "
                        f"(sim={semantic_similarity:.3f}) → {semantic_boost:.1f}x boost"
                    )

            # Apply all boosts
            combined_boost = domain_boost * size_boost * semantic_boost
            final_score = base_score / combined_boost

            metadata = {
                "base_score": base_score,
                "domain_boost": domain_boost,
                "size_boost": size_boost,
                "semantic_boost": semantic_boost,
                "semantic_similarity": semantic_similarity,
                "combined_boost": combined_boost,
                "final_score": final_score,
                "cost_norm": cost_norm,
                "speed_norm": speed_norm,
                "quality_norm": quality_norm,
            }

            scored.append((model, final_score, metadata))

        # Sort by score (lower is better)
        scored.sort(key=lambda x: x[1])

        return scored

    def _normalize_cost(self, cost: float, models: list[ModelConfig]) -> float:
        """Normalize cost to 0-1 range."""
        costs = [m.cost for m in models]
        min_cost = min(costs)
        max_cost = max(costs)

        if max_cost == min_cost:
            return 0.0

        return (cost - min_cost) / (max_cost - min_cost)

    def _normalize_speed(self, speed_ms: int, models: list[ModelConfig]) -> float:
        """Normalize speed to 0-1 range."""
        speeds = [m.speed_ms for m in models]
        min_speed = min(speeds)
        max_speed = max(speeds)

        if max_speed == min_speed:
            return 0.0

        return (speed_ms - min_speed) / (max_speed - min_speed)

    def _normalize_quality(self, quality: float, models: list[ModelConfig]) -> float:
        """Normalize quality to 0-1 range."""
        qualities = [m.quality_score for m in models]
        min_quality = min(qualities)
        max_quality = max(qualities)

        if max_quality == min_quality:
            return 1.0

        return (quality - min_quality) / (max_quality - min_quality)


class LatencyAwareExecutionPlanner:
    """Create execution plans with latency awareness."""

    def __init__(self):
        self.scorer = ModelScorer()

    async def create_plan(
        self,
        query: str,
        complexity: QueryComplexity,
        available_models: list[ModelConfig],
        tier: Optional[UserTier] = None,
        workflow: Optional[WorkflowProfile] = None,
        force_models: Optional[list[str]] = None,
        max_latency_ms: Optional[int] = None,
        max_budget: Optional[float] = None,
        quality_threshold: Optional[float] = None,
        query_domains: Optional[list[str]] = None,
        semantic_hints: Optional[dict[str, float]] = None,
    ) -> ExecutionPlan:
        """
        Create execution plan for query.

        Args:
            query: User query
            complexity: Detected complexity level
            available_models: Models to choose from
            tier: User tier (optional)
            workflow: Workflow profile (optional)
            force_models: Force specific models (optional)
            max_latency_ms: Maximum latency constraint
            max_budget: Maximum cost constraint
            quality_threshold: Minimum quality required
            query_domains: Detected domains (optional)
            semantic_hints: Semantic similarity scores (optional)
        """
        # Get optimization weights
        if workflow and workflow.optimization_override:
            optimization = workflow.optimization_override
        elif tier:
            optimization = tier.optimization
        else:
            from .config import OptimizationWeights

            optimization = OptimizationWeights(cost=0.33, speed=0.33, quality=0.34)

        # Score models with all signals
        scored_models = self.scorer.score_models(
            available_models, query, complexity, optimization, query_domains, semantic_hints
        )

        # Capture auto-detected domains for metadata
        if query_domains is None:
            query_domains = self.scorer.domain_detector.detect(query)

        if not scored_models:
            raise ValueError("No models available after scoring")

        best_model, best_score, best_meta = scored_models[0]

        # Enhanced logging with semantic info
        log_msg = (
            f"Top model: {best_model.name} "
            f"(score: {best_score:.3f}, "
            f"domain_boost: {best_meta['domain_boost']:.1f}x"
        )
        if best_meta.get("semantic_boost", 1.0) > 1.0:
            log_msg += f", semantic_boost: {best_meta['semantic_boost']:.1f}x"
        log_msg += ")"
        logger.info(log_msg)

        # Initialize variables
        drafter = None
        verifier = None
        race_models = None

        # Determine strategy
        if complexity == QueryComplexity.TRIVIAL:
            strategy = ExecutionStrategy.DIRECT_CHEAP
            primary = min(available_models, key=lambda m: m.cost)
            reasoning = "Trivial query → cheapest model"

        elif complexity == QueryComplexity.SIMPLE:
            strategy = ExecutionStrategy.DIRECT_SMART
            primary = best_model
            reasoning = (
                f"Simple query → best scored model "
                f"(domain_boost: {best_meta['domain_boost']:.1f}x"
            )
            if best_meta.get("semantic_boost", 1.0) > 1.0:
                reasoning += f", semantic_boost: {best_meta['semantic_boost']:.1f}x"
            reasoning += ")"

        elif complexity == QueryComplexity.MODERATE:
            if tier and tier.enable_speculative and len(scored_models) >= 2:
                drafter = scored_models[0][0]
                verifier = scored_models[1][0]

                max_latency = max_latency_ms or (tier.latency.max_total_ms if tier else 10000)
                combined_latency = drafter.speed_ms + verifier.speed_ms

                if combined_latency < max_latency:
                    strategy = ExecutionStrategy.SPECULATIVE
                    primary = None
                    reasoning = (
                        f"Moderate query → speculative " f"({drafter.name} → {verifier.name})"
                    )
                else:
                    strategy = ExecutionStrategy.DIRECT_SMART
                    primary = best_model
                    reasoning = "Moderate query → direct " "(speculative exceeds latency budget)"
            else:
                strategy = ExecutionStrategy.DIRECT_SMART
                primary = best_model
                reasoning = "Moderate query → best scored model"

        elif complexity in [QueryComplexity.HARD, QueryComplexity.EXPERT]:
            if tier and tier.enable_parallel and len(scored_models) >= tier.parallel_race_count:
                strategy = ExecutionStrategy.PARALLEL_RACE
                primary = None
                race_models = [m for m, _, _ in scored_models[: tier.parallel_race_count]]
                reasoning = f"Complex query → parallel race " f"({len(race_models)} models)"
            else:
                strategy = ExecutionStrategy.DIRECT_BEST
                primary = max(available_models, key=lambda m: m.quality_score)
                reasoning = "Complex query → best quality model"

        else:
            strategy = ExecutionStrategy.DIRECT_SMART
            primary = best_model
            reasoning = "Default → best scored model"

        plan = ExecutionPlan(
            strategy=strategy,
            primary_model=(
                primary
                if strategy
                in [
                    ExecutionStrategy.DIRECT_CHEAP,
                    ExecutionStrategy.DIRECT_BEST,
                    ExecutionStrategy.DIRECT_SMART,
                ]
                else None
            ),
            drafter=drafter if strategy == ExecutionStrategy.SPECULATIVE else None,
            verifier=verifier if strategy == ExecutionStrategy.SPECULATIVE else None,
            race_models=race_models if strategy == ExecutionStrategy.PARALLEL_RACE else None,
            estimated_cost=self._estimate_cost(strategy, primary, drafter, verifier, race_models),
            estimated_latency_ms=self._estimate_latency(
                strategy, primary, drafter, verifier, race_models
            ),
            reasoning=reasoning,
            metadata={
                "complexity": complexity.value,
                "query_domains": query_domains,
                "semantic_routing_used": semantic_hints is not None,
                "optimization": {
                    "cost": optimization.cost,
                    "speed": optimization.speed,
                    "quality": optimization.quality,
                },
                "top_3_models": [
                    {"name": m.name, "score": s, **meta} for m, s, meta in scored_models[:3]
                ],
            },
        )

        return plan

    def _estimate_cost(
        self,
        strategy: ExecutionStrategy,
        primary: Optional[ModelConfig],
        drafter: Optional[ModelConfig],
        verifier: Optional[ModelConfig],
        race_models: Optional[list[ModelConfig]],
    ) -> float:
        """Estimate execution cost."""
        if strategy == ExecutionStrategy.SPECULATIVE:
            return drafter.cost + (0.5 * verifier.cost)
        elif strategy == ExecutionStrategy.PARALLEL_RACE:
            return sum(m.cost for m in race_models)
        else:
            return primary.cost if primary else 0.0

    def _estimate_latency(
        self,
        strategy: ExecutionStrategy,
        primary: Optional[ModelConfig],
        drafter: Optional[ModelConfig],
        verifier: Optional[ModelConfig],
        race_models: Optional[list[ModelConfig]],
    ) -> float:
        """Estimate execution latency."""
        if strategy == ExecutionStrategy.SPECULATIVE:
            return max(drafter.speed_ms, verifier.speed_ms)
        elif strategy == ExecutionStrategy.PARALLEL_RACE:
            return min(m.speed_ms for m in race_models)
        else:
            return primary.speed_ms if primary else 0.0


# ==================== EXPORTS ====================

__all__ = [
    # Enums
    "ExecutionStrategy",
    # Data classes
    "ExecutionPlan",
    # Core classes
    "DomainDetector",
    "ModelScorer",
    "LatencyAwareExecutionPlanner",
]
