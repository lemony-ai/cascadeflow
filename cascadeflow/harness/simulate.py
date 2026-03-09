"""
Offline cascade simulation for config tuning.

Replay queries through different cascade configurations without making
real API calls. Uses the deterministic routing/complexity/domain detection
pipeline to project cost, latency, and escalation rate changes.

Example:
    >>> from cascadeflow.harness.simulate import simulate
    >>> from cascadeflow.schema.config import ModelConfig
    >>>
    >>> queries = ["What is Python?", "Prove the Riemann hypothesis"]
    >>> result = simulate(
    ...     queries=queries,
    ...     models=[
    ...         ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.000375),
    ...         ModelConfig(name="gpt-4o", provider="openai", cost=0.005),
    ...     ],
    ...     quality_threshold=0.7,
    ... )
    >>> print(f"Projected cost: ${result.projected_cost:.4f}")
    >>> print(f"Escalation rate: {result.escalation_rate:.1%}")
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class SimulationEntry:
    """Result of simulating a single query."""

    query: str
    complexity: str
    domain: str
    domain_confidence: float
    routing_decision: str
    projected_model: str
    projected_cost: float


@dataclass
class SimulationResult:
    """
    Aggregate result from offline cascade simulation.

    Provides projected metrics for the given cascade configuration
    without making any real API calls.
    """

    total_queries: int
    projected_cost: float
    escalation_rate: float
    model_distribution: dict[str, int]
    complexity_distribution: dict[str, int]
    domain_distribution: dict[str, int]
    per_query: list[SimulationEntry] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """Return a summary dict suitable for logging or display."""
        return {
            "total_queries": self.total_queries,
            "projected_cost": round(self.projected_cost, 6),
            "escalation_rate": round(self.escalation_rate, 4),
            "model_distribution": self.model_distribution,
            "complexity_distribution": self.complexity_distribution,
            "domain_distribution": self.domain_distribution,
        }

    def compare(self, other: "SimulationResult") -> dict[str, Any]:
        """Compare two simulation results and return the diff."""
        cost_diff = self.projected_cost - other.projected_cost
        cost_pct = (cost_diff / other.projected_cost * 100) if other.projected_cost > 0 else 0
        return {
            "cost_change": round(cost_diff, 6),
            "cost_change_pct": round(cost_pct, 2),
            "escalation_rate_change": round(
                self.escalation_rate - other.escalation_rate, 4
            ),
            "this": self.summary(),
            "other": other.summary(),
        }


def simulate(
    queries: Union[list[str], str, Path],
    models: list[Any],
    quality_threshold: float = 0.7,
    domain_detection: bool = True,
) -> SimulationResult:
    """
    Simulate cascade routing for a list of queries without making API calls.

    Uses the deterministic complexity detection and domain routing pipeline
    to project which model would handle each query under the given config.

    Args:
        queries: List of query strings, or path to a JSONL file where each
            line has a "query" field (as exported by session.save()).
        models: List of ModelConfig objects ordered from cheapest to most
            expensive. At minimum, provide 2 models (draft + verifier).
        quality_threshold: Quality threshold for cascade decisions. Lower
            thresholds mean fewer escalations (more cost savings, potentially
            lower quality).
        domain_detection: Whether to use domain detection for routing.

    Returns:
        SimulationResult with projected metrics and per-query breakdown.
    """
    from cascadeflow.quality.complexity import ComplexityDetector, QueryComplexity

    query_list = _load_queries(queries)
    if not query_list:
        return SimulationResult(
            total_queries=0,
            projected_cost=0.0,
            escalation_rate=0.0,
            model_distribution={},
            complexity_distribution={},
            domain_distribution={},
        )

    if len(models) < 2:
        raise ValueError("simulate() requires at least 2 models (draft + verifier)")

    complexity_detector = ComplexityDetector()

    draft_model = models[0]
    verifier_model = models[-1]
    draft_cost = getattr(draft_model, "cost", 0.0) or 0.0
    verifier_cost = getattr(verifier_model, "cost", 0.0) or 0.0
    draft_name = getattr(draft_model, "name", str(draft_model))
    verifier_name = getattr(verifier_model, "name", str(verifier_model))

    detector = None
    if domain_detection:
        try:
            from cascadeflow.routing.domain import DomainDetector

            detector = DomainDetector()
        except Exception:
            logger.debug("Domain detection unavailable, using complexity only")

    entries: list[SimulationEntry] = []
    model_dist: dict[str, int] = {}
    complexity_dist: dict[str, int] = {}
    domain_dist: dict[str, int] = {}
    total_cost = 0.0
    escalated = 0

    # Complexity levels that get escalated to verifier
    escalation_levels = {QueryComplexity.HARD.value, QueryComplexity.EXPERT.value}

    # Adjust escalation threshold based on quality_threshold
    # Lower threshold = more aggressive (fewer escalations)
    if quality_threshold < 0.5:
        escalation_levels = {QueryComplexity.EXPERT.value}
    elif quality_threshold > 0.85:
        escalation_levels = {
            QueryComplexity.MODERATE.value,
            QueryComplexity.HARD.value,
            QueryComplexity.EXPERT.value,
        }

    for query in query_list:
        complexity_result = complexity_detector.detect(query)
        if isinstance(complexity_result, tuple):
            complexity_enum = complexity_result[0]
        else:
            complexity_enum = complexity_result
        complexity_str = complexity_enum.value if hasattr(complexity_enum, "value") else str(complexity_enum)

        domain_str = "general"
        domain_conf = 0.0
        if detector:
            try:
                domain_result = detector.detect(query)
                if isinstance(domain_result, tuple):
                    domain_str = str(domain_result[0])
                    domain_conf = float(domain_result[1]) if len(domain_result) > 1 else 0.0
                elif hasattr(domain_result, "domain"):
                    domain_str = str(domain_result.domain)
                    domain_conf = getattr(domain_result, "confidence", 0.0)
            except Exception:
                pass

        needs_escalation = complexity_str in escalation_levels
        if needs_escalation:
            projected_model = verifier_name
            query_cost = verifier_cost + draft_cost  # Draft attempt + verifier
            routing = "escalated"
            escalated += 1
        else:
            projected_model = draft_name
            query_cost = draft_cost
            routing = "draft_accepted"

        total_cost += query_cost
        model_dist[projected_model] = model_dist.get(projected_model, 0) + 1
        complexity_dist[complexity_str] = complexity_dist.get(complexity_str, 0) + 1
        domain_dist[domain_str] = domain_dist.get(domain_str, 0) + 1

        entries.append(
            SimulationEntry(
                query=query[:200],
                complexity=complexity_str,
                domain=domain_str,
                domain_confidence=domain_conf,
                routing_decision=routing,
                projected_model=projected_model,
                projected_cost=query_cost,
            )
        )

    n = len(query_list)
    return SimulationResult(
        total_queries=n,
        projected_cost=total_cost,
        escalation_rate=escalated / n if n > 0 else 0.0,
        model_distribution=model_dist,
        complexity_distribution=complexity_dist,
        domain_distribution=domain_dist,
        per_query=entries,
    )


def _load_queries(queries: Union[list[str], str, Path]) -> list[str]:
    """Load queries from a list, file path, or JSONL file."""
    if isinstance(queries, list):
        return queries

    path = Path(queries)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    result: list[str] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict) and "query" in data:
                    result.append(data["query"])
                elif isinstance(data, str):
                    result.append(data)
            except json.JSONDecodeError:
                result.append(line)
    return result
