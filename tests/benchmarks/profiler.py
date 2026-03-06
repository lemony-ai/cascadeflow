"""Performance profiling for cascade components.

Profiles internal cascade operations to identify bottlenecks:
- Quality scorer latency and accuracy
- Domain detector latency and accuracy
- Alignment scorer effectiveness
- Cascade decision overhead
- Model inference time breakdown
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ComponentProfile:
    """Profile data for a single cascade component."""

    component_name: str  # e.g., "quality_scorer", "domain_detector"
    invocations: int = 0  # Number of times component was called
    total_latency_ms: float = 0.0  # Total latency across all invocations
    avg_latency_ms: float = 0.0  # Average latency per invocation
    min_latency_ms: float = float("inf")  # Minimum latency observed
    max_latency_ms: float = 0.0  # Maximum latency observed
    accuracy: Optional[float] = None  # Accuracy if applicable (0-1)
    errors: int = 0  # Number of errors encountered

    def record_invocation(self, latency_ms: float, error: bool = False):
        """Record a single invocation of this component."""
        self.invocations += 1
        self.total_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        self.avg_latency_ms = self.total_latency_ms / self.invocations

        if error:
            self.errors += 1


@dataclass
class CascadeProfile:
    """Complete profiling data for a cascade operation."""

    # Component profiles
    quality_scorer: ComponentProfile = field(
        default_factory=lambda: ComponentProfile("quality_scorer")
    )
    domain_detector: ComponentProfile = field(
        default_factory=lambda: ComponentProfile("domain_detector")
    )
    alignment_scorer: ComponentProfile = field(
        default_factory=lambda: ComponentProfile("alignment_scorer")
    )

    # Model inference timing
    drafter_inference_ms: float = 0.0
    verifier_inference_ms: float = 0.0

    # Cascade decision overhead
    cascade_decision_ms: float = 0.0  # Time spent in cascade logic (excluding model calls)

    # Total timing
    total_latency_ms: float = 0.0

    def latency_breakdown(self) -> dict[str, float]:
        """Get breakdown of latency by component."""
        return {
            "drafter_inference": self.drafter_inference_ms,
            "verifier_inference": self.verifier_inference_ms,
            "quality_scorer": self.quality_scorer.total_latency_ms,
            "domain_detector": self.domain_detector.total_latency_ms,
            "alignment_scorer": self.alignment_scorer.total_latency_ms,
            "cascade_decision_overhead": self.cascade_decision_ms,
            "total": self.total_latency_ms,
        }

    def component_summary(self) -> dict[str, dict[str, float]]:
        """Get summary statistics for each component."""
        return {
            "quality_scorer": {
                "invocations": self.quality_scorer.invocations,
                "avg_latency_ms": self.quality_scorer.avg_latency_ms,
                "total_latency_ms": self.quality_scorer.total_latency_ms,
                "min_latency_ms": (
                    self.quality_scorer.min_latency_ms if self.quality_scorer.invocations > 0 else 0
                ),
                "max_latency_ms": self.quality_scorer.max_latency_ms,
                "errors": self.quality_scorer.errors,
            },
            "domain_detector": {
                "invocations": self.domain_detector.invocations,
                "avg_latency_ms": self.domain_detector.avg_latency_ms,
                "total_latency_ms": self.domain_detector.total_latency_ms,
                "min_latency_ms": (
                    self.domain_detector.min_latency_ms
                    if self.domain_detector.invocations > 0
                    else 0
                ),
                "max_latency_ms": self.domain_detector.max_latency_ms,
                "errors": self.domain_detector.errors,
            },
            "alignment_scorer": {
                "invocations": self.alignment_scorer.invocations,
                "avg_latency_ms": self.alignment_scorer.avg_latency_ms,
                "total_latency_ms": self.alignment_scorer.total_latency_ms,
                "min_latency_ms": (
                    self.alignment_scorer.min_latency_ms
                    if self.alignment_scorer.invocations > 0
                    else 0
                ),
                "max_latency_ms": self.alignment_scorer.max_latency_ms,
                "errors": self.alignment_scorer.errors,
            },
        }


class CascadeProfiler:
    """Profiler for cascade operations."""

    def __init__(self):
        """Initialize profiler."""
        self.profiles: list[CascadeProfile] = []

    def start_profile(self) -> CascadeProfile:
        """Start a new profile for a cascade operation."""
        profile = CascadeProfile()
        self.profiles.append(profile)
        return profile

    def aggregate_profiles(self) -> dict[str, any]:
        """Aggregate all profiles into summary statistics."""
        if not self.profiles:
            return {
                "total_operations": 0,
                "avg_latency_ms": 0.0,
                "latency_breakdown": {},
                "component_stats": {},
            }

        total_ops = len(self.profiles)

        # Aggregate latency breakdown
        breakdown = {
            "drafter_inference": 0.0,
            "verifier_inference": 0.0,
            "quality_scorer": 0.0,
            "domain_detector": 0.0,
            "alignment_scorer": 0.0,
            "cascade_decision_overhead": 0.0,
            "total": 0.0,
        }

        for profile in self.profiles:
            lb = profile.latency_breakdown()
            for key in breakdown:
                breakdown[key] += lb[key]

        # Calculate averages
        for key in breakdown:
            breakdown[key] /= total_ops

        # Aggregate component stats
        component_totals = {
            "quality_scorer": {"invocations": 0, "total_latency_ms": 0.0, "errors": 0},
            "domain_detector": {"invocations": 0, "total_latency_ms": 0.0, "errors": 0},
            "alignment_scorer": {
                "invocations": 0,
                "total_latency_ms": 0.0,
                "errors": 0,
            },
        }

        for profile in self.profiles:
            component_totals["quality_scorer"]["invocations"] += profile.quality_scorer.invocations
            component_totals["quality_scorer"][
                "total_latency_ms"
            ] += profile.quality_scorer.total_latency_ms
            component_totals["quality_scorer"]["errors"] += profile.quality_scorer.errors

            component_totals["domain_detector"][
                "invocations"
            ] += profile.domain_detector.invocations
            component_totals["domain_detector"][
                "total_latency_ms"
            ] += profile.domain_detector.total_latency_ms
            component_totals["domain_detector"]["errors"] += profile.domain_detector.errors

            component_totals["alignment_scorer"][
                "invocations"
            ] += profile.alignment_scorer.invocations
            component_totals["alignment_scorer"][
                "total_latency_ms"
            ] += profile.alignment_scorer.total_latency_ms
            component_totals["alignment_scorer"]["errors"] += profile.alignment_scorer.errors

        # Calculate average latencies
        component_stats = {}
        for component, totals in component_totals.items():
            avg_latency = (
                totals["total_latency_ms"] / totals["invocations"]
                if totals["invocations"] > 0
                else 0.0
            )
            component_stats[component] = {
                "total_invocations": totals["invocations"],
                "avg_latency_ms": avg_latency,
                "total_latency_ms": totals["total_latency_ms"],
                "errors": totals["errors"],
                "error_rate": (
                    totals["errors"] / totals["invocations"] if totals["invocations"] > 0 else 0.0
                ),
            }

        return {
            "total_operations": total_ops,
            "avg_latency_ms": breakdown["total"],
            "latency_breakdown_avg": breakdown,
            "component_stats": component_stats,
        }

    def print_summary(self):
        """Print profiling summary to console."""
        summary = self.aggregate_profiles()

        print("\n" + "=" * 80)
        print("CASCADE PROFILING SUMMARY")
        print("=" * 80 + "\n")

        print(f"Total Operations: {summary['total_operations']}")
        print(f"Average Total Latency: {summary['avg_latency_ms']:.2f}ms\n")

        print("LATENCY BREAKDOWN (Average per operation):")
        breakdown = summary["latency_breakdown_avg"]
        print(f"  Drafter Inference:       {breakdown['drafter_inference']:.2f}ms")
        print(f"  Verifier Inference:      {breakdown['verifier_inference']:.2f}ms")
        print(f"  Quality Scorer:          {breakdown['quality_scorer']:.2f}ms")
        print(f"  Domain Detector:         {breakdown['domain_detector']:.2f}ms")
        print(f"  Alignment Scorer:        {breakdown['alignment_scorer']:.2f}ms")
        print(f"  Cascade Decision:        {breakdown['cascade_decision_overhead']:.2f}ms")
        print(f"  Total:                   {breakdown['total']:.2f}ms\n")

        # Calculate percentages
        total = breakdown["total"]
        if total > 0:
            print("LATENCY PERCENTAGE BREAKDOWN:")
            print(f"  Drafter Inference:       {breakdown['drafter_inference']/total*100:.1f}%")
            print(f"  Verifier Inference:      {breakdown['verifier_inference']/total*100:.1f}%")
            print(f"  Quality Scorer:          {breakdown['quality_scorer']/total*100:.1f}%")
            print(f"  Domain Detector:         {breakdown['domain_detector']/total*100:.1f}%")
            print(f"  Alignment Scorer:        {breakdown['alignment_scorer']/total*100:.1f}%")
            print(
                f"  Cascade Decision:        {breakdown['cascade_decision_overhead']/total*100:.1f}%\n"
            )

        print("COMPONENT STATISTICS:")
        for component, stats in summary["component_stats"].items():
            print(f"\n  {component.replace('_', ' ').title()}:")
            print(f"    Total Invocations:   {stats['total_invocations']}")
            print(f"    Avg Latency:         {stats['avg_latency_ms']:.2f}ms")
            print(f"    Total Latency:       {stats['total_latency_ms']:.2f}ms")
            print(f"    Errors:              {stats['errors']}")
            print(f"    Error Rate:          {stats['error_rate']*100:.2f}%")

        # Identify bottlenecks
        print("\nBOTTLENECK ANALYSIS:")
        sorted_components = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
        print("  Top 3 latency contributors:")
        for i, (component, latency) in enumerate(sorted_components[:3], 1):
            pct = (latency / total * 100) if total > 0 else 0
            print(f"    {i}. {component.replace('_', ' ').title()}: {latency:.2f}ms ({pct:.1f}%)")

        print("\n" + "=" * 80 + "\n")
