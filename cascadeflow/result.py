"""Result classes for CascadeFlow."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class CascadeResult:
    """
    Result from a cascade execution.

    Contains all information about the cascade, including which models
    were tried, costs, quality scores, and the final response.

    Example:
        >>> result = await agent.run("What is AI?")
        >>> print(f"Used: {result.model_used}")
        >>> print(f"Cost: ${result.total_cost:.6f}")
        >>> print(f"Cascaded: {result.cascaded}")
    """

    # Required fields (NO defaults) - must come first!
    content: str
    model_used: str
    provider: str
    total_cost: float
    total_tokens: int
    confidence: float

    # Optional fields (WITH defaults) - must come after!
    cost_breakdown: Dict[str, float] = field(default_factory=dict)
    token_breakdown: Dict[str, int] = field(default_factory=dict)
    quality_threshold_met: bool = True
    cascaded: bool = False
    cascade_path: List[str] = field(default_factory=list)
    attempts: int = 1
    latency_ms: float = 0.0
    latency_breakdown: Dict[str, float] = field(default_factory=dict)
    user_id: Optional[str] = None
    user_tier: Optional[str] = None
    user_credits_used: float = 0.0
    user_credits_remaining: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    budget_exceeded: bool = False
    budget_remaining: float = 0.0

    def __str__(self) -> str:
        """String representation."""
        return (
            f"CascadeResult(\n"
            f"  model={self.model_used},\n"
            f"  cost=${self.total_cost:.6f},\n"
            f"  tokens={self.total_tokens},\n"
            f"  confidence={self.confidence:.2f},\n"
            f"  cascaded={self.cascaded},\n"
            f"  latency={self.latency_ms:.0f}ms\n"
            f")"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "model_used": self.model_used,
            "provider": self.provider,
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens,
            "confidence": self.confidence,
            "cascaded": self.cascaded,
            "cascade_path": self.cascade_path,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
            "user_tier": self.user_tier,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }