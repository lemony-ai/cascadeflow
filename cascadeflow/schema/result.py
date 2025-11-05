"""
Result Dataclasses for cascadeflow
===================================

This module contains result types returned by cascade operations.

Core Classes:
    - CascadeResult: Comprehensive result object with 30+ diagnostic fields

Fields Included:
    - Core fields (9): content, model_used, total_cost, latency_ms, etc.
    - Quality diagnostics (4): quality_score, threshold, pass/fail status
    - Timing breakdown (5): complexity detection, draft/verifier timing, overhead
    - Cost breakdown (3): draft_cost, verifier_cost, cost_saved
    - Tool calling (2): tool_calls, has_tool_calls

Usage:
    >>> result = await agent.run("What is Python?")
    >>> print(f"Model: {result.model_used}")
    >>> print(f"Cost: ${result.total_cost:.6f}")
    >>> print(f"Draft accepted: {result.draft_accepted}")

See Also:
    - schema.config.ModelConfig for model configuration
    - core.cascade.SpeculativeResult for internal cascade results
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CascadeResult:
    """
    Result from cascade agent execution with comprehensive diagnostics.

    Core Fields:
        content: Generated response text
        model_used: Name of model that produced final response
        total_cost: Total cost in dollars (FIXED: properly aggregated)
        latency_ms: Total latency in milliseconds
        complexity: Detected complexity level
        cascaded: Whether cascade was used
        draft_accepted: If cascaded, whether draft was accepted
        routing_strategy: How query was routed ("direct" or "cascade")
        reason: Explanation for routing decision

    Tool Calling (v2.3+):
        tool_calls: List of tool calls made by model (if any)
        has_tool_calls: Whether response includes tool calls

    Quality System Diagnostics:
        quality_score: Quality score from validator (0-1)
        quality_threshold: Threshold used for validation
        quality_check_passed: Whether quality check passed
        rejection_reason: Why draft was rejected (if applicable)

    Response Tracking:
        draft_response: Full draft response text (for validation)
        verifier_response: Full verifier response text (if cascaded)
        response_length: Length of final response
        response_word_count: Word count of final response

    Timing Breakdown:
        complexity_detection_ms: Time to detect complexity
        draft_generation_ms: Time to generate draft
        quality_verification_ms: Time for quality validation
        verifier_generation_ms: Time to generate verifier response
        cascade_overhead_ms: Additional overhead from cascade system

    Cost Breakdown (v2.5 - FIXED):
        draft_cost: Cost of draft generation
        verifier_cost: Cost of verifier generation
        cost_saved: Cost saved vs always using best model
    """

    # Core fields
    content: str
    model_used: str
    total_cost: float  # FIXED: Now properly aggregated
    latency_ms: float
    complexity: str
    cascaded: bool
    draft_accepted: bool
    routing_strategy: str
    reason: str

    # Tool calling
    tool_calls: Optional[list[dict[str, Any]]] = None
    has_tool_calls: bool = False

    # Quality system diagnostics
    quality_score: Optional[float] = None
    quality_threshold: Optional[float] = None
    quality_check_passed: Optional[bool] = None
    rejection_reason: Optional[str] = None

    # Response tracking
    draft_response: Optional[str] = None
    verifier_response: Optional[str] = None
    response_length: Optional[int] = None
    response_word_count: Optional[int] = None

    # Timing breakdown
    complexity_detection_ms: Optional[float] = None
    draft_generation_ms: Optional[float] = None
    quality_verification_ms: Optional[float] = None
    verifier_generation_ms: Optional[float] = None
    cascade_overhead_ms: Optional[float] = None

    # Cost breakdown (v2.5 - FIXED)
    draft_cost: Optional[float] = None
    verifier_cost: Optional[float] = None
    cost_saved: Optional[float] = None

    # Model information
    draft_model: Optional[str] = None
    draft_latency_ms: Optional[float] = None
    draft_confidence: Optional[float] = None
    verifier_model: Optional[str] = None
    verifier_latency_ms: Optional[float] = None
    verifier_confidence: Optional[float] = None

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "content": self.content,
            "model_used": self.model_used,
            "total_cost": self.total_cost,
            "latency_ms": self.latency_ms,
            "complexity": self.complexity,
            "cascaded": self.cascaded,
            "draft_accepted": self.draft_accepted,
            "routing_strategy": self.routing_strategy,
            "reason": self.reason,
            "tool_calls": self.tool_calls,
            "has_tool_calls": self.has_tool_calls,
            "quality_score": self.quality_score,
            "quality_threshold": self.quality_threshold,
            "quality_check_passed": self.quality_check_passed,
            "rejection_reason": self.rejection_reason,
            "response_length": self.response_length,
            "response_word_count": self.response_word_count,
            "timing_breakdown": {
                "complexity_detection_ms": self.complexity_detection_ms,
                "draft_generation_ms": self.draft_generation_ms,
                "quality_verification_ms": self.quality_verification_ms,
                "verifier_generation_ms": self.verifier_generation_ms,
                "cascade_overhead_ms": self.cascade_overhead_ms,
            },
            "cost_breakdown": {
                "draft_cost": self.draft_cost,
                "verifier_cost": self.verifier_cost,
                "cost_saved": self.cost_saved,
            },
            "metadata": self.metadata,
        }


# ==================== EXPORTS ====================

__all__ = ["CascadeResult"]
