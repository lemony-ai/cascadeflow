"""Report generation for benchmark results."""

import json
from pathlib import Path
from typing import List, Optional

from .base import BenchmarkResult, BenchmarkSummary


class BenchmarkReporter:
    """Generate reports from benchmark results."""

    def __init__(self, output_dir: str = "benchmarks/results"):
        """
        Initialize reporter.

        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_json(
        self,
        summary: BenchmarkSummary,
        results: list[BenchmarkResult],
        filename: Optional[str] = None,
    ) -> Path:
        """
        Export benchmark results to JSON.

        Args:
            summary: Benchmark summary
            results: List of individual results
            filename: Output filename (default: <dataset>_results.json)

        Returns:
            Path to exported JSON file
        """
        if filename is None:
            filename = f"{summary.dataset_name.lower()}_results.json"

        filepath = self.output_dir / filename

        data = {
            "summary": {
                "dataset_name": summary.dataset_name,
                "total_tests": summary.total_tests,
                "successful_tests": summary.successful_tests,
                "failed_tests": summary.failed_tests,
                "drafter_accepted": summary.drafter_accepted,
                "escalated_to_verifier": summary.escalated_to_verifier,
                "acceptance_rate_pct": summary.acceptance_rate_pct,
                "escalation_rate_pct": summary.escalation_rate_pct,
                "direct_routed": summary.direct_routed,
                "direct_routing_pct": summary.direct_routing_pct,
                "total_cost": summary.total_cost,
                "total_baseline_cost": summary.total_baseline_cost,
                "total_savings": summary.total_savings,
                "avg_savings_pct": summary.avg_savings_pct,
                "avg_cost_per_query": summary.avg_cost_per_query,
                "avg_latency_ms": summary.avg_latency_ms,
                "median_latency_ms": summary.median_latency_ms,
                "p95_latency_ms": summary.p95_latency_ms,
                "avg_cascadeflow_latency_ms": summary.avg_cascadeflow_latency_ms,
                "accuracy": summary.accuracy,
                "drafter_accuracy": summary.drafter_accuracy,
                "verifier_accuracy": summary.verifier_accuracy,
                "direct_accuracy": summary.direct_accuracy,
                "total_input_tokens": summary.total_input_tokens,
                "total_output_tokens": summary.total_output_tokens,
            },
            "results": [
                {
                    "test_id": r.test_id,
                    "query": r.query[:100] + "..." if len(r.query) > 100 else r.query,
                    "model_used": r.model_used,
                    "accepted": r.accepted,
                    "routing_strategy": r.routing_strategy,
                    "quality_score": r.quality_score,
                    "total_cost": r.total_cost,
                    "baseline_cost": r.baseline_cost,
                    "cost_savings_pct": r.cost_savings_pct,
                    "latency_ms": r.latency_ms,
                    "cascadeflow_latency_ms": r.cascadeflow_latency_ms,
                    "is_correct": r.is_correct,
                    "error": r.error,
                }
                for r in results
            ],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        return filepath

    def export_csv(
        self,
        results: list[BenchmarkResult],
        filename: Optional[str] = None,
    ) -> Path:
        """
        Export detailed results to CSV.

        Args:
            results: List of benchmark results
            filename: Output filename (default: <dataset>_detailed.csv)

        Returns:
            Path to exported CSV file
        """
        if not results:
            raise ValueError("No results to export")

        if filename is None:
            filename = f"{results[0].dataset_name.lower()}_detailed.csv"

        filepath = self.output_dir / filename

        import csv

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(
                [
                    "test_id",
                    "model_used",
                    "accepted",
                    "routing_strategy",
                    "quality_score",
                    "drafter_cost",
                    "verifier_cost",
                    "total_cost",
                    "baseline_cost",
                    "cost_savings",
                    "cost_savings_pct",
                    "latency_ms",
                    "cascadeflow_latency_ms",
                    "tokens_input",
                    "tokens_output",
                    "is_correct",
                    "error",
                ]
            )

            # Rows
            for r in results:
                writer.writerow(
                    [
                        r.test_id,
                        r.model_used,
                        r.accepted,
                        r.routing_strategy,
                        f"{r.quality_score:.3f}",
                        f"{r.drafter_cost:.6f}",
                        f"{r.verifier_cost:.6f}",
                        f"{r.total_cost:.6f}",
                        f"{r.baseline_cost:.6f}",
                        f"{r.cost_savings:.6f}",
                        f"{r.cost_savings_pct:.1f}",
                        f"{r.latency_ms:.0f}",
                        f"{r.cascadeflow_latency_ms:.0f}",
                        r.tokens_input,
                        r.tokens_output,
                        r.is_correct,
                        r.error or "",
                    ]
                )

        return filepath

    def generate_markdown_report(
        self,
        summary: BenchmarkSummary,
        results: list[BenchmarkResult],
        filename: Optional[str] = None,
    ) -> Path:
        """
        Generate markdown report.

        Args:
            summary: Benchmark summary
            results: List of benchmark results
            filename: Output filename (default: <dataset>_report.md)

        Returns:
            Path to generated markdown file
        """
        if filename is None:
            filename = f"{summary.dataset_name.lower()}_report.md"

        filepath = self.output_dir / filename

        # Generate report content
        content = f"""# {summary.dataset_name} Benchmark Report

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | {summary.total_tests} |
| Successful | {summary.successful_tests} |
| Failed | {summary.failed_tests} |
| **Drafter Accepted** | **{summary.drafter_accepted} ({summary.acceptance_rate_pct:.1f}%)** |
| **Escalated to Verifier** | **{summary.escalated_to_verifier} ({summary.escalation_rate_pct:.1f}%)** |
| **Direct Routed** | **{summary.direct_routed} ({summary.direct_routing_pct:.1f}%)** |

## Cost Analysis

| Metric | Value |
|--------|-------|
| Total Cost | ${summary.total_cost:.6f} |
| Baseline Cost (always-powerful-model) | ${summary.total_baseline_cost:.6f} |
| **Total Savings** | **${summary.total_savings:.6f} ({summary.avg_savings_pct:.1f}%)** |
| Average Cost per Query | ${summary.avg_cost_per_query:.6f} |

### Cost Breakdown
- Drafter Cost: ${summary.total_cost - summary.total_savings:.6f}
- Verifier Cost: ${summary.total_savings:.6f}

## Performance

| Metric | Value |
|--------|-------|
| Average Latency | {summary.avg_latency_ms:.0f}ms |
| Median Latency | {summary.median_latency_ms:.0f}ms |
| P95 Latency | {summary.p95_latency_ms:.0f}ms |
| Average Cascade Overhead | {summary.avg_cascadeflow_latency_ms:.0f}ms |

## Quality

| Metric | Value |
|--------|-------|
| Overall Accuracy | {summary.accuracy:.1f}% |
| Drafter Accuracy | {summary.drafter_accuracy:.1f}% |
| Verifier Accuracy | {summary.verifier_accuracy:.1f}% |
| Direct Accuracy | {summary.direct_accuracy:.1f}% |

## Token Usage

| Metric | Value |
|--------|-------|
| Total Input Tokens | {summary.total_input_tokens:,} |
| Total Output Tokens | {summary.total_output_tokens:,} |
| Average Input Tokens | {summary.avg_input_tokens:.0f} |
| Average Output Tokens | {summary.avg_output_tokens:.0f} |

## ROI Calculation

If you process **1,000,000 queries per month**:

- **Baseline Cost**: ${summary.total_baseline_cost / summary.successful_tests * 1000000:.2f}/month
- **Cascade Cost**: ${summary.total_cost / summary.successful_tests * 1000000:.2f}/month
- **Monthly Savings**: ${summary.total_savings / summary.successful_tests * 1000000:.2f}
- **Annual Savings**: ${summary.total_savings / summary.successful_tests * 1000000 * 12:.2f}

---

*Report generated from {summary.successful_tests} successful tests*
"""

        with open(filepath, "w") as f:
            f.write(content)

        return filepath
