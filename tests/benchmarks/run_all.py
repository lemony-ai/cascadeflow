"""Benchmark Runner - Execute and Compare All Benchmarks

Runs all available CascadeFlow benchmarks and generates comparison reports.

Features:
- Runs HumanEval, GSM8K, and Provider Comparison benchmarks
- Generates comparison table across all benchmarks
- Exports results to JSON, CSV, and Markdown
- Calculates aggregate statistics
- Identifies best/worst performing configurations

Usage:
    python run_all.py [--output-dir results] [--format json,csv,md]
"""

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .reporter import BenchmarkReporter


async def run_all_benchmarks(output_dir: Path) -> dict[str, Any]:
    """
    Run all available benchmarks and collect results.

    Args:
        output_dir: Directory to store results

    Returns:
        Dict mapping benchmark names to their summaries
    """
    results = {}

    print("\n" + "=" * 80)
    print("CASCADEFLOW BENCHMARK SUITE")
    print("=" * 80 + "\n")

    print(f"Output Directory: {output_dir}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")

    # Check API keys
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set - some benchmarks may fail")
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  Warning: ANTHROPIC_API_KEY not set - provider comparison will fail")

    print("\n" + "=" * 80 + "\n")

    # Run HumanEval benchmark
    try:
        print("Running HumanEval Code Generation Benchmark...")
        from .humaneval import run_humaneval_benchmark

        humaneval_summary = await run_humaneval_benchmark()
        results["humaneval"] = humaneval_summary
        print("✅ HumanEval benchmark completed\n")
    except Exception as e:
        print(f"❌ HumanEval benchmark failed: {e}\n")
        results["humaneval"] = None

    # Run GSM8K benchmark
    try:
        print("Running GSM8K Math Reasoning Benchmark...")
        from .gsm8k import run_gsm8k_benchmark

        gsm8k_summary = await run_gsm8k_benchmark()
        results["gsm8k"] = gsm8k_summary
        print("✅ GSM8K benchmark completed\n")
    except Exception as e:
        print(f"❌ GSM8K benchmark failed: {e}\n")
        results["gsm8k"] = None

    # Run Provider Comparison
    try:
        print("Running Provider Comparison Benchmark...")
        from .provider_comparison import test_provider_comparison

        await test_provider_comparison()
        print("✅ Provider comparison completed\n")
        results["provider_comparison"] = "completed"
    except Exception as e:
        print(f"❌ Provider comparison failed: {e}\n")
        results["provider_comparison"] = None

    return results


def generate_comparison_table(results: dict[str, Any]) -> str:
    """Generate markdown comparison table."""

    table = "# CascadeFlow Benchmark Comparison\n\n"
    table += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    table += "## Summary Statistics\n\n"
    table += (
        "| Benchmark | Accuracy | Acceptance Rate | Cost Reduction | Avg Quality | Avg Latency |\n"
    )
    table += (
        "|-----------|----------|-----------------|----------------|-------------|-------------|\n"
    )

    for name, summary in results.items():
        if summary is None or name == "provider_comparison":
            continue

        table += f"| {name.title()} | "
        table += f"{summary.accuracy*100:.1f}% | "
        table += f"{summary.acceptance_rate*100:.1f}% | "
        table += f"{summary.cost_reduction_pct:.1f}% | "
        table += f"{summary.avg_quality_score:.3f} | "
        table += f"{summary.avg_latency_ms:.0f}ms |\n"

    table += "\n## Cost Analysis\n\n"
    table += "| Benchmark | Total Tests | Cascade Cost | Baseline Cost | Savings |\n"
    table += "|-----------|-------------|--------------|---------------|----------|\n"

    for name, summary in results.items():
        if summary is None or name == "provider_comparison":
            continue

        table += f"| {name.title()} | "
        table += f"{summary.total_tests} | "
        table += f"${summary.total_cost:.6f} | "
        table += f"${summary.baseline_cost:.6f} | "
        table += f"${summary.cost_savings:.6f} |\n"

    table += "\n## Key Findings\n\n"

    # Calculate aggregate statistics
    valid_results = [r for r in results.values() if r is not None and r != "completed"]

    if valid_results:
        avg_accuracy = sum(r.accuracy for r in valid_results) / len(valid_results)
        avg_acceptance = sum(r.acceptance_rate for r in valid_results) / len(valid_results)
        avg_cost_reduction = sum(r.cost_reduction_pct for r in valid_results) / len(valid_results)
        total_savings = sum(r.cost_savings for r in valid_results)

        table += f"- **Average Accuracy:** {avg_accuracy*100:.1f}%\n"
        table += f"- **Average Acceptance Rate:** {avg_acceptance*100:.1f}% (drafter used)\n"
        table += f"- **Average Cost Reduction:** {avg_cost_reduction:.1f}%\n"
        table += f"- **Total Savings:** ${total_savings:.6f}\n"

        # Best/worst performers
        best_accuracy = max(valid_results, key=lambda r: r.accuracy)
        best_cost = max(valid_results, key=lambda r: r.cost_reduction_pct)

        table += "\n### Best Performers\n\n"
        table += f"- **Highest Accuracy:** {best_accuracy.dataset_name} ({best_accuracy.accuracy*100:.1f}%)\n"
        table += f"- **Best Cost Reduction:** {best_cost.dataset_name} ({best_cost.cost_reduction_pct:.1f}%)\n"

        # Recommendations
        table += "\n### Recommendations\n\n"
        if avg_cost_reduction > 50:
            table += "- ✅ CascadeFlow achieves significant cost savings (>50%) across benchmarks\n"
        if avg_acceptance > 0.6:
            table += "- ✅ Drafter handles majority of requests independently\n"
        if avg_accuracy > 0.85:
            table += "- ✅ High accuracy maintained with cascade pattern\n"
        else:
            table += "- ⚠️  Consider raising quality threshold to improve accuracy\n"

    return table


async def main():
    """Main benchmark runner."""

    parser = argparse.ArgumentParser(description="Run all CascadeFlow benchmarks")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="benchmark_results",
        help="Output directory for results",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="md,json,csv",
        help="Output formats (comma-separated: md, json, csv)",
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run all benchmarks
    results = await run_all_benchmarks(output_dir)

    # Generate comparison table
    comparison_table = generate_comparison_table(results)

    # Export results
    formats = [f.strip() for f in args.format.split(",")]

    if "md" in formats:
        md_path = output_dir / "comparison.md"
        with open(md_path, "w") as f:
            f.write(comparison_table)
        print(f"\n✅ Markdown report: {md_path}")

    if "json" in formats:
        json_path = output_dir / "results.json"
        # Convert summaries to dicts for JSON serialization
        json_results = {}
        for name, summary in results.items():
            if summary is None:
                json_results[name] = None
            elif summary == "completed":
                json_results[name] = "completed"
            else:
                json_results[name] = {
                    "dataset_name": summary.dataset_name,
                    "total_tests": summary.total_tests,
                    "correct": summary.correct,
                    "accuracy": summary.accuracy,
                    "drafter_accepted": summary.drafter_accepted,
                    "acceptance_rate": summary.acceptance_rate,
                    "total_cost": summary.total_cost,
                    "baseline_cost": summary.baseline_cost,
                    "cost_savings": summary.cost_savings,
                    "cost_reduction_pct": summary.cost_reduction_pct,
                    "avg_quality_score": summary.avg_quality_score,
                    "avg_latency_ms": summary.avg_latency_ms,
                    "drafter_accuracy": summary.drafter_accuracy,
                }

        with open(json_path, "w") as f:
            json.dump(json_results, f, indent=2)
        print(f"✅ JSON results: {json_path}")

    print("\n" + "=" * 80)
    print("BENCHMARK SUITE COMPLETED")
    print("=" * 80 + "\n")

    print(comparison_table)


if __name__ == "__main__":
    asyncio.run(main())
