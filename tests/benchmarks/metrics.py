"""Metrics calculation utilities for benchmarks."""

from dataclasses import dataclass
from typing import List

from .base import BenchmarkResult


@dataclass
class CostMetrics:
    """Cost-related metrics."""

    total_cost: float
    total_baseline_cost: float
    total_savings: float
    savings_percentage: float
    avg_cost_per_query: float
    drafter_cost: float
    verifier_cost: float

    @staticmethod
    def from_results(results: list[BenchmarkResult]) -> "CostMetrics":
        """Calculate cost metrics from benchmark results."""
        if not results:
            return CostMetrics(
                total_cost=0.0,
                total_baseline_cost=0.0,
                total_savings=0.0,
                savings_percentage=0.0,
                avg_cost_per_query=0.0,
                drafter_cost=0.0,
                verifier_cost=0.0,
            )

        total_cost = sum(r.total_cost for r in results)
        total_baseline = sum(r.baseline_cost for r in results)
        total_savings = total_baseline - total_cost
        savings_pct = (total_savings / total_baseline * 100) if total_baseline > 0 else 0.0

        return CostMetrics(
            total_cost=total_cost,
            total_baseline_cost=total_baseline,
            total_savings=total_savings,
            savings_percentage=savings_pct,
            avg_cost_per_query=total_cost / len(results),
            drafter_cost=sum(r.drafter_cost for r in results),
            verifier_cost=sum(r.verifier_cost for r in results),
        )


@dataclass
class LatencyMetrics:
    """Latency-related metrics."""

    avg_latency_ms: float
    median_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float

    @staticmethod
    def from_results(results: list[BenchmarkResult]) -> "LatencyMetrics":
        """Calculate latency metrics from benchmark results."""
        if not results:
            return LatencyMetrics(
                avg_latency_ms=0.0,
                median_latency_ms=0.0,
                min_latency_ms=0.0,
                max_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
            )

        latencies = sorted([r.latency_ms for r in results])

        return LatencyMetrics(
            avg_latency_ms=sum(latencies) / len(latencies),
            median_latency_ms=latencies[len(latencies) // 2],
            min_latency_ms=min(latencies),
            max_latency_ms=max(latencies),
            p95_latency_ms=latencies[int(len(latencies) * 0.95)],
            p99_latency_ms=latencies[int(len(latencies) * 0.99)],
        )


@dataclass
class QualityMetrics:
    """Quality-related metrics."""

    overall_accuracy: float
    drafter_accuracy: float
    verifier_accuracy: float
    direct_accuracy: float
    total_correct: int
    total_incorrect: int
    drafter_correct: int
    drafter_incorrect: int
    verifier_correct: int
    verifier_incorrect: int
    direct_correct: int
    direct_incorrect: int

    @staticmethod
    def from_results(results: list[BenchmarkResult]) -> "QualityMetrics":
        """Calculate quality metrics from benchmark results."""
        if not results:
            return QualityMetrics(
                overall_accuracy=0.0,
                drafter_accuracy=0.0,
                verifier_accuracy=0.0,
                direct_accuracy=0.0,
                total_correct=0,
                total_incorrect=0,
                drafter_correct=0,
                drafter_incorrect=0,
                verifier_correct=0,
                verifier_incorrect=0,
                direct_correct=0,
                direct_incorrect=0,
            )

        # Overall
        total_correct = sum(1 for r in results if r.is_correct)
        total_incorrect = len(results) - total_correct
        overall_accuracy = (total_correct / len(results) * 100) if results else 0.0

        # Drafter
        drafter_results = [r for r in results if r.routing_strategy == "cascade" and r.accepted]
        drafter_correct = sum(1 for r in drafter_results if r.is_correct)
        drafter_incorrect = len(drafter_results) - drafter_correct
        drafter_accuracy = (
            (drafter_correct / len(drafter_results) * 100) if drafter_results else 0.0
        )

        # Verifier
        verifier_results = [r for r in results if r.verifier_rejected]
        verifier_correct = sum(1 for r in verifier_results if r.is_correct)
        verifier_incorrect = len(verifier_results) - verifier_correct
        verifier_accuracy = (
            (verifier_correct / len(verifier_results) * 100) if verifier_results else 0.0
        )

        # Direct
        direct_results = [r for r in results if r.direct_routed]
        direct_correct = sum(1 for r in direct_results if r.is_correct)
        direct_incorrect = len(direct_results) - direct_correct
        direct_accuracy = (direct_correct / len(direct_results) * 100) if direct_results else 0.0

        return QualityMetrics(
            overall_accuracy=overall_accuracy,
            drafter_accuracy=drafter_accuracy,
            verifier_accuracy=verifier_accuracy,
            direct_accuracy=direct_accuracy,
            total_correct=total_correct,
            total_incorrect=total_incorrect,
            drafter_correct=drafter_correct,
            drafter_incorrect=drafter_incorrect,
            verifier_correct=verifier_correct,
            verifier_incorrect=verifier_incorrect,
            direct_correct=direct_correct,
            direct_incorrect=direct_incorrect,
        )
