"""
Core cascade execution engine.

This module contains:
- Execution planning and strategy selection
- Domain detection and model scoring
- Speculative cascade implementation
- Batch processing (v0.2.1+)

All submodule imports are lazy (PEP 562) to avoid pulling in heavy
dependencies (e.g. litellm via batch) at ``import cascadeflow`` time.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .batch import BatchProcessingError, BatchProcessor, BatchResult
    from .batch_config import BatchConfig, BatchStrategy
    from .cascade import SpeculativeCascade, SpeculativeResult, WholeResponseCascade
    from .execution import (
        DomainDetector,
        ExecutionPlan,
        ExecutionStrategy,
        LatencyAwareExecutionPlanner,
        ModelScorer,
    )

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Cascade
    "SpeculativeCascade": (".cascade", "SpeculativeCascade"),
    "SpeculativeResult": (".cascade", "SpeculativeResult"),
    "WholeResponseCascade": (".cascade", "WholeResponseCascade"),
    # Execution
    "DomainDetector": (".execution", "DomainDetector"),
    "ExecutionPlan": (".execution", "ExecutionPlan"),
    "ExecutionStrategy": (".execution", "ExecutionStrategy"),
    "LatencyAwareExecutionPlanner": (".execution", "LatencyAwareExecutionPlanner"),
    "ModelScorer": (".execution", "ModelScorer"),
    # Batch config (lightweight — no litellm)
    "BatchConfig": (".batch_config", "BatchConfig"),
    "BatchStrategy": (".batch_config", "BatchStrategy"),
    # Batch processing (heavy — imports litellm)
    "BatchProcessor": (".batch", "BatchProcessor"),
    "BatchResult": (".batch", "BatchResult"),
    "BatchProcessingError": (".batch", "BatchProcessingError"),
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        import importlib

        module = importlib.import_module(module_path, __package__)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return list(__all__) + list(_LAZY_IMPORTS)


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
