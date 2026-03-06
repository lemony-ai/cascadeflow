"""Benchmark framework components."""

from .base import Benchmark, BenchmarkResult, BenchmarkSummary
from .metrics import CostMetrics, LatencyMetrics, QualityMetrics
from .profiler import CascadeProfile, CascadeProfiler, ComponentProfile
from .reporter import BenchmarkReporter
from .benchmark_config import (
    BenchmarkConfig,
    BenchmarkMode,
    BenchmarkTargets,
    DomainBenchmarkConfig,
    DEFAULT_TARGETS,
    DRAFTER_MODELS,
    VERIFIER_MODELS,
    DOMAIN_CONFIGS,
)

# Reproducibility pipeline
from .repro import ReproMetadata, collect_repro_metadata, metadata_to_dict
from .baseline import (
    BaselineArtifact,
    BenchmarkDelta,
    ComparisonReport,
    GoNoGoResult,
    save_baseline,
    load_baseline,
    compare_to_baseline,
    check_go_nogo,
)
from .harness_overhead import OverheadReport, measure_harness_overhead
from .observe_validation import ObserveValidationResult, validate_observe_mode
from .artifact import bundle_artifact

__all__ = [
    # Base classes
    "Benchmark",
    "BenchmarkResult",
    "BenchmarkSummary",
    # Metrics
    "CostMetrics",
    "LatencyMetrics",
    "QualityMetrics",
    # Reporter
    "BenchmarkReporter",
    # Profiler
    "CascadeProfile",
    "CascadeProfiler",
    "ComponentProfile",
    # Configuration
    "BenchmarkConfig",
    "BenchmarkMode",
    "BenchmarkTargets",
    "DomainBenchmarkConfig",
    "DEFAULT_TARGETS",
    "DRAFTER_MODELS",
    "VERIFIER_MODELS",
    "DOMAIN_CONFIGS",
    # Reproducibility pipeline
    "ReproMetadata",
    "collect_repro_metadata",
    "metadata_to_dict",
    "BaselineArtifact",
    "BenchmarkDelta",
    "ComparisonReport",
    "GoNoGoResult",
    "save_baseline",
    "load_baseline",
    "compare_to_baseline",
    "check_go_nogo",
    "OverheadReport",
    "measure_harness_overhead",
    "ObserveValidationResult",
    "validate_observe_mode",
    "bundle_artifact",
]
