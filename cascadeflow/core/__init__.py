"""
Core cascade execution engine.

This module contains:
- Execution planning and strategy selection
- Domain detection and model scoring
- Speculative cascade implementation
"""

from .cascade import (
    SpeculativeCascade,
    SpeculativeResult,
    WholeResponseCascade,
)
from .execution import (
    DomainDetector,
    ExecutionPlan,
    ExecutionStrategy,
    LatencyAwareExecutionPlanner,
    ModelScorer,
)

__all__ = [
    # Execution
    "DomainDetector",
    "ExecutionPlan",
    "ExecutionStrategy",
    "LatencyAwareExecutionPlanner",
    "ModelScorer",
    # Cascade
    "WholeResponseCascade",
    "SpeculativeCascade",
    "SpeculativeResult",
]
