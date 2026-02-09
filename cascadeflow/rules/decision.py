"""Rule engine decision output."""

from dataclasses import dataclass, field
from typing import Any, Optional

from cascadeflow.routing.base import RoutingStrategy


@dataclass
class RuleDecision:
    """Decision produced by the rule engine."""

    routing_strategy: Optional[RoutingStrategy] = None
    reason: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    preferred_channel: Optional[str] = None
    model_name: Optional[str] = None
    allowed_models: Optional[list[str]] = None
    excluded_models: Optional[list[str]] = None
    preferred_models: Optional[list[str]] = None
    forced_models: Optional[list[str]] = None
    quality_threshold: Optional[float] = None
    max_budget: Optional[float] = None
    failover_channel: Optional[str] = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence must be 0-1, got {self.confidence}")

    def is_override(self) -> bool:
        return self.routing_strategy is not None
