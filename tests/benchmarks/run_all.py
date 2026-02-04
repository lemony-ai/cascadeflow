"""Benchmark Runner - Execute and Compare All Benchmarks

Runs all available CascadeFlow benchmarks and generates comparison reports.

Features:
- Runs HumanEval, GSM8K, MT-Bench, TruthfulQA, and Provider Comparison benchmarks
- Generates comparison table across all benchmarks
- Exports results to JSON, CSV, and Markdown
- Calculates aggregate statistics
- Identifies best/worst performing configurations

Usage:
    python run_all.py [--output-dir results] [--format json,csv,md] [--full] [--verbose-routing]
"""

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .reporter import BenchmarkReporter


async def run_all_benchmarks(
    output_dir: Path,
    *,
    full: bool = False,
    verbose_routing: bool = False,
) -> dict[str, Any]:
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

    if verbose_routing:
        os.environ["CASCADEFLOW_BENCH_LOG"] = "1"

    # Run HumanEval benchmark
    try:
        print("Running HumanEval Code Generation Benchmark...")
        from .humaneval import run_humaneval_benchmark

        humaneval_summary = await run_humaneval_benchmark(max_samples=None if full else 10)
        results["humaneval"] = humaneval_summary
        print("✅ HumanEval benchmark completed\n")
    except Exception as e:
        print(f"❌ HumanEval benchmark failed: {e}\n")
        results["humaneval"] = None

    # Run GSM8K benchmark
    try:
        print("Running GSM8K Math Reasoning Benchmark...")
        from .gsm8k import run_gsm8k_benchmark

        gsm8k_summary = await run_gsm8k_benchmark(max_samples=None if full else 10)
        results["gsm8k"] = gsm8k_summary
        print("✅ GSM8K benchmark completed\n")
    except Exception as e:
        print(f"❌ GSM8K benchmark failed: {e}\n")
        results["gsm8k"] = None

    # Run MT-Bench
    try:
        print("Running MT-Bench Multi-Turn Conversation Benchmark...")
        from .mtbench import run_mtbench_benchmark

        mtbench_summary = await run_mtbench_benchmark(max_samples=None if full else 10)
        results["mtbench"] = mtbench_summary
        print("✅ MT-Bench benchmark completed\n")
    except Exception as e:
        print(f"❌ MT-Bench benchmark failed: {e}\n")
        results["mtbench"] = None

    # Run TruthfulQA
    try:
        print("Running TruthfulQA Factual Accuracy Benchmark...")
        from .truthfulqa import run_truthfulqa_benchmark

        truthfulqa_summary = await run_truthfulqa_benchmark(max_samples=None if full else 15)
        results["truthfulqa"] = truthfulqa_summary
        print("✅ TruthfulQA benchmark completed\n")
    except Exception as e:
        print(f"❌ TruthfulQA benchmark failed: {e}\n")
        results["truthfulqa"] = None

    # Run Banking77 (official full set)
    try:
        print("Running Banking77 Intent Classification Benchmark...")
        from .banking77_benchmark import run_banking77_benchmark

        banking_summary = await run_banking77_benchmark(
            max_samples=None if full else 200, split="test"
        )
        results["banking77"] = banking_summary
        print("✅ Banking77 benchmark completed\n")
    except Exception as e:
        print(f"❌ Banking77 benchmark failed: {e}\n")
        results["banking77"] = None

    # Run Customer Support
    try:
        print("Running Customer Support Benchmark...")
        from .customer_support import run_customer_support_benchmark

        customer_summary = await run_customer_support_benchmark(max_samples=None if full else 20)
        results["customer_support"] = customer_summary
        print("✅ Customer support benchmark completed\n")
    except Exception as e:
        print(f"❌ Customer support benchmark failed: {e}\n")
        results["customer_support"] = None

    # Run Agentic Tool-Calling Benchmark
    try:
        print("Running Agentic Tool-Calling Benchmark...")
        from .bfcl.agentic_benchmark import AgenticBenchmark

        agentic_benchmark = AgenticBenchmark(
            drafter_model="claude-haiku-4-5-20251001",
            verifier_model="claude-opus-4-5-20251101",
        )
        agentic_summary = await agentic_benchmark.run_benchmark()
        results["agentic"] = agentic_summary
        print("✅ Agentic benchmark completed\n")
    except Exception as e:
        print(f"❌ Agentic benchmark failed: {e}\n")
        results["agentic"] = None

    # Run Structured Tool-Calling Benchmark
    try:
        print("Running Structured Tool-Calling Benchmark...")
        from .tool_calls import run_tool_calls_benchmark

        tool_calls_summary = await run_tool_calls_benchmark()
        results["tool_calls"] = tool_calls_summary
        print("✅ Structured tool-calling benchmark completed\n")
    except Exception as e:
        print(f"❌ Structured tool-calling benchmark failed: {e}\n")
        results["tool_calls"] = None

    # Run Agentic Structured Tool-Calling Benchmark
    try:
        print("Running Agentic Structured Tool-Calling Benchmark...")
        from .tool_calls_agentic import run_tool_calls_agentic_benchmark

        tool_calls_agentic_summary = await run_tool_calls_agentic_benchmark()
        results["tool_calls_agentic"] = tool_calls_agentic_summary
        print("✅ Agentic structured tool-calling benchmark completed\n")
    except Exception as e:
        print(f"❌ Agentic structured tool-calling benchmark failed: {e}\n")
        results["tool_calls_agentic"] = None

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
    table += "| Benchmark | Accuracy | Acceptance Rate | Avg Savings | Drafter Accuracy | Avg Latency |\n"
    table += "|-----------|----------|-----------------|-------------|------------------|-------------|\n"

    for name, summary in results.items():
        if summary is None or name == "provider_comparison" or not hasattr(summary, "total_tests"):
            continue

        display_name = getattr(summary, "dataset_name", name.title())
        table += f"| {display_name} | "
        table += f"{summary.accuracy:.1f}% | "
        table += f"{summary.acceptance_rate_pct:.1f}% | "
        table += f"{summary.avg_savings_pct:.1f}% | "
        table += f"{summary.drafter_accuracy:.1f}% | "
        table += f"{summary.avg_latency_ms:.0f}ms |\n"

    table += "\n## Cost Analysis\n\n"
    table += "| Benchmark | Total Tests | Cascade Cost | Baseline Cost | Savings |\n"
    table += "|-----------|-------------|--------------|---------------|----------|\n"

    for name, summary in results.items():
        if summary is None or name == "provider_comparison" or not hasattr(summary, "total_tests"):
            continue

        display_name = getattr(summary, "dataset_name", name.title())
        table += f"| {display_name} | "
        table += f"{summary.total_tests} | "
        table += f"${summary.total_cost:.6f} | "
        table += f"${summary.total_baseline_cost:.6f} | "
        table += f"${summary.total_savings:.6f} |\n"

    agentic_summary = results.get("agentic")
    if isinstance(agentic_summary, dict):
        table += "\n## Agentic Tool-Calling Summary\n\n"
        table += f"- **Total Tasks:** {agentic_summary.get('total_tasks', 0)}\n"
        table += f"- **Accuracy:** {agentic_summary.get('accuracy', 0) * 100:.1f}%\n"
        table += (
            f"- **Draft Acceptance:** {agentic_summary.get('draft_acceptance', 0) * 100:.1f}%\n"
        )
        table += f"- **Dependency Handling:** {agentic_summary.get('dependency_handling', 0) * 100:.1f}%\n"
        table += f"- **Total Cost:** ${agentic_summary.get('total_cost', 0):.6f}\n"

        natural = agentic_summary.get("natural_language", {})
        explicit = agentic_summary.get("explicit_steps", {})
        if natural or explicit:
            table += "\n### Prompt Style Split\n\n"
            if natural:
                table += (
                    f"- **Natural Language:** "
                    f"{natural.get('accuracy', 0) * 100:.1f}% accuracy, "
                    f"{natural.get('draft_rate', 0) * 100:.1f}% draft acceptance\n"
                )
            if explicit:
                table += (
                    f"- **Explicit Steps:** "
                    f"{explicit.get('accuracy', 0) * 100:.1f}% accuracy, "
                    f"{explicit.get('draft_rate', 0) * 100:.1f}% draft acceptance\n"
                )

    table += "\n## Key Findings\n\n"

    # Calculate aggregate statistics
    valid_results = [
        r
        for r in results.values()
        if r is not None and r != "completed" and hasattr(r, "total_tests")
    ]

    if valid_results:
        avg_accuracy = sum(r.accuracy for r in valid_results) / len(valid_results)
        avg_acceptance = sum(r.acceptance_rate_pct for r in valid_results) / len(valid_results)
        avg_cost_reduction = sum(r.avg_savings_pct for r in valid_results) / len(valid_results)
        total_savings = sum(r.total_savings for r in valid_results)

        table += f"- **Average Accuracy:** {avg_accuracy:.1f}%\n"
        table += f"- **Average Acceptance Rate:** {avg_acceptance:.1f}% (drafter used)\n"
        table += f"- **Average Cost Reduction:** {avg_cost_reduction:.1f}%\n"
        table += f"- **Total Savings:** ${total_savings:.6f}\n"

        # Best/worst performers
        best_accuracy = max(valid_results, key=lambda r: r.accuracy)
        best_cost = max(valid_results, key=lambda r: r.avg_savings_pct)

        table += "\n### Best Performers\n\n"
        table += f"- **Highest Accuracy:** {best_accuracy.dataset_name} ({best_accuracy.accuracy:.1f}%)\n"
        table += f"- **Best Cost Reduction:** {best_cost.dataset_name} ({best_cost.avg_savings_pct:.1f}%)\n"

        # Recommendations
        table += "\n### Recommendations\n\n"
        if avg_cost_reduction > 50:
            table += "- ✅ CascadeFlow achieves significant cost savings (>50%) across benchmarks\n"
        if avg_acceptance > 60:
            table += "- ✅ Drafter handles majority of requests independently\n"
        if avg_accuracy > 85:
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
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full official datasets (may be slow and expensive)",
    )
    parser.add_argument(
        "--verbose-routing",
        action="store_true",
        help="Log routing decisions during benchmark runs",
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run all benchmarks
    results = await run_all_benchmarks(
        output_dir,
        full=args.full,
        verbose_routing=args.verbose_routing,
    )

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
            elif isinstance(summary, dict):
                json_results[name] = summary
            else:
                json_results[name] = {
                    "dataset_name": summary.dataset_name,
                    "total_tests": summary.total_tests,
                    "successful_tests": summary.successful_tests,
                    "failed_tests": summary.failed_tests,
                    "accuracy": summary.accuracy,
                    "drafter_accepted": summary.drafter_accepted,
                    "acceptance_rate_pct": summary.acceptance_rate_pct,
                    "escalation_rate_pct": summary.escalation_rate_pct,
                    "total_cost": summary.total_cost,
                    "total_baseline_cost": summary.total_baseline_cost,
                    "total_savings": summary.total_savings,
                    "avg_savings_pct": summary.avg_savings_pct,
                    "avg_latency_ms": summary.avg_latency_ms,
                    "drafter_accuracy": summary.drafter_accuracy,
                    "verifier_accuracy": summary.verifier_accuracy,
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
