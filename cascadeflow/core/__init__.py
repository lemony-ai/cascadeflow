"""
Core cascade execution engine.

This module contains:
- Execution planning and strategy selection
- Domain detection and model scoring
- Speculative cascade implementation
- Batch processing (v0.2.1+)
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
from .batch_config import BatchConfig, BatchStrategy
from .batch import BatchProcessor, BatchResult, BatchProcessingError

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
    # Batch Processing (v0.2.1+)
    "BatchConfig",
    "BatchStrategy",
    "BatchProcessor",
    "BatchResult",
    "BatchProcessingError",
]
