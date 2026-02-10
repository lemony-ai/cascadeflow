#!/usr/bin/env python3
"""CascadeFlow Benchmark Runner.

Runs all benchmarks (MT-Bench, MMLU, GSM8K) with various configurations
to measure cost reduction and quality retention.

Targets:
- MT-Bench: ≥85% cost reduction, ≥95% quality retention
- MMLU: ≥45% cost reduction, ≥95% quality retention
- GSM8K: ≥35% cost reduction, ≥95% quality retention

Usage:
    # Run all benchmarks with full configuration
    python run_benchmarks.py

    # Run specific benchmark
    python run_benchmarks.py --benchmark mtbench

    # Run with specific mode
    python run_benchmarks.py --mode baseline

    # Run quick test (reduced samples)
    python run_benchmarks.py --quick
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from tests.benchmarks.benchmark_config import (
    DEFAULT_TARGETS,
    BenchmarkConfig,
    BenchmarkMode,
    BenchmarkTargets,
    print_config,
)


async def run_gsm8k_benchmark(config: BenchmarkConfig, max_samples: int = 10) -> dict[str, Any]:
    """Run GSM8K benchmark with given configuration."""
    from tests.benchmarks.gsm8k import GSM8KBenchmark

    benchmark = GSM8KBenchmark(
        drafter_model=config.default_drafter,
        verifier_model=config.default_verifier,
        quality_threshold=config.default_quality_threshold,
        max_samples=max_samples,
    )

    # Note: The current GSM8K benchmark doesn't support semantic/domain config
    # We'll run it and return basic metrics
    summary = await benchmark.run()

    return {
        "benchmark": "GSM8K",
        "mode": config.mode.value,
        "accuracy": getattr(summary, "accuracy", 0),
        "cost_reduction_pct": getattr(summary, "avg_savings_pct", 0),
        "drafter_acceptance_rate": getattr(summary, "acceptance_rate_pct", 0),
        "total_cost": getattr(summary, "total_cost", 0),
        "baseline_cost": getattr(summary, "total_baseline_cost", 0),
    }


async def run_mtbench_benchmark(config: BenchmarkConfig, max_samples: int = 10) -> dict[str, Any]:
    """Run MT-Bench benchmark with given configuration."""
    from tests.benchmarks.mtbench import MTBenchmark

    benchmark = MTBenchmark(
        drafter_model=config.default_drafter,
        verifier_model=config.default_verifier,
        max_samples=max_samples,
    )

    summary = await benchmark.run()

    return {
        "benchmark": "MT-Bench",
        "mode": config.mode.value,
        "accuracy": getattr(summary, "accuracy", 0),
        "cost_reduction_pct": getattr(summary, "avg_savings_pct", 0),
        "drafter_acceptance_rate": getattr(summary, "acceptance_rate_pct", 0),
        "total_cost": getattr(summary, "total_cost", 0),
        "baseline_cost": getattr(summary, "total_baseline_cost", 0),
    }


async def run_mmlu_benchmark(config: BenchmarkConfig, max_samples: int = 40) -> dict[str, Any]:
    """Run MMLU benchmark with given configuration."""
    from tests.benchmarks.mmlu import MMLUBenchmark

    benchmark = MMLUBenchmark(
        drafter_model=config.default_drafter,
        verifier_model=config.default_verifier,
        quality_threshold=config.default_quality_threshold,
        max_samples=max_samples,
        config=config,
    )

    summary = await benchmark.run()

    return {
        "benchmark": "MMLU",
        "mode": config.mode.value,
        "accuracy": getattr(summary, "accuracy", 0),
        "cost_reduction_pct": getattr(summary, "avg_savings_pct", 0),
        "drafter_acceptance_rate": getattr(summary, "acceptance_rate_pct", 0),
        "total_cost": getattr(summary, "total_cost", 0),
        "baseline_cost": getattr(summary, "total_baseline_cost", 0),
    }


def check_targets(results: dict[str, Any], targets: BenchmarkTargets) -> dict[str, bool]:
    """Check if benchmark results meet targets."""
    checks = {}

    for result in results.get("benchmarks", []):
        benchmark = result.get("benchmark", "")
        cost_reduction = result.get("cost_reduction_pct", 0)
        accuracy = result.get("accuracy", 0)

        # Assume baseline accuracy is 100% (GPT-4o), so quality retention = accuracy
        quality_retention = accuracy

        if benchmark == "MT-Bench":
            checks["MT-Bench"] = targets.check_mt_bench(cost_reduction, quality_retention)
        elif benchmark == "MMLU":
            checks["MMLU"] = targets.check_mmlu(cost_reduction, quality_retention)
        elif benchmark == "GSM8K":
            checks["GSM8K"] = targets.check_gsm8k(cost_reduction, quality_retention)

    return checks


def print_results_table(results: list[dict[str, Any]], targets: BenchmarkTargets) -> None:
    """Print results in a formatted table."""
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 80)

    # Header
    print(
        f"\n{'Benchmark':<12} {'Mode':<15} {'Accuracy':<10} {'Cost Red.':<12} {'Drafter %':<10} {'Target Met':<12}"
    )
    print("-" * 80)

    for result in results:
        benchmark = result.get("benchmark", "")
        mode = result.get("mode", "")
        accuracy = result.get("accuracy", 0)
        cost_reduction = result.get("cost_reduction_pct", 0)
        drafter_rate = result.get("drafter_acceptance_rate", 0)

        # Check target
        if benchmark == "MT-Bench":
            target_met = (
                cost_reduction >= targets.mt_bench_cost_reduction
                and accuracy >= targets.quality_retention
            )
            target_str = f"≥{targets.mt_bench_cost_reduction}%"
        elif benchmark == "MMLU":
            target_met = (
                cost_reduction >= targets.mmlu_cost_reduction
                and accuracy >= targets.quality_retention
            )
            target_str = f"≥{targets.mmlu_cost_reduction}%"
        elif benchmark == "GSM8K":
            target_met = (
                cost_reduction >= targets.gsm8k_cost_reduction
                and accuracy >= targets.quality_retention
            )
            target_str = f"≥{targets.gsm8k_cost_reduction}%"
        else:
            target_met = False
            target_str = "N/A"

        status = "✅ PASS" if target_met else "❌ FAIL"

        print(
            f"{benchmark:<12} {mode:<15} {accuracy:>7.1f}% {cost_reduction:>9.1f}% {drafter_rate:>9.1f}% {status:<12}"
        )

    print("-" * 80)


def save_results(results: dict[str, Any], output_path: str) -> None:
    """Save results to JSON file."""
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


async def run_all_benchmarks(
    mode: BenchmarkMode = BenchmarkMode.FULL,
    benchmarks: Optional[list[str]] = None,
    quick: bool = False,
) -> dict[str, Any]:
    """
    Run all specified benchmarks.

    Args:
        mode: Configuration mode (baseline, semantic_only, domain_only, full)
        benchmarks: List of benchmarks to run (mtbench, mmlu, gsm8k)
        quick: If True, use reduced sample sizes

    Returns:
        Results dictionary
    """
    print("\n" + "=" * 80)
    print("CASCADEFLOW BENCHMARK SUITE")
    print("=" * 80)
    print(f"\nStarted: {datetime.now().isoformat()}")
    print(f"Mode: {mode.value}")

    # Create config based on mode
    if mode == BenchmarkMode.BASELINE:
        config = BenchmarkConfig.baseline()
    elif mode == BenchmarkMode.SEMANTIC_ONLY:
        config = BenchmarkConfig.semantic_only()
    elif mode == BenchmarkMode.DOMAIN_ONLY:
        config = BenchmarkConfig.domain_only()
    else:
        config = BenchmarkConfig.full()

    print_config(config)

    # Determine which benchmarks to run
    if benchmarks is None:
        benchmarks = ["gsm8k", "mmlu", "mtbench"]

    # Sample sizes
    if quick:
        gsm8k_samples = 5
        mmlu_samples = 10
        mtbench_samples = 5
    else:
        gsm8k_samples = 10
        mmlu_samples = 40
        mtbench_samples = 10

    results = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode.value,
        "config": {
            "drafter": config.default_drafter,
            "verifier": config.default_verifier,
            "quality_threshold": config.default_quality_threshold,
            "semantic_detection": config.enable_semantic_detection,
            "domain_pipeline": config.enable_domain_pipeline,
        },
        "benchmarks": [],
    }

    # Run benchmarks
    if "gsm8k" in benchmarks:
        print("\n" + "=" * 80)
        print("Running GSM8K Benchmark...")
        print("=" * 80)
        try:
            gsm8k_config = BenchmarkConfig.for_gsm8k(mode)
            gsm8k_result = await run_gsm8k_benchmark(gsm8k_config, gsm8k_samples)
            results["benchmarks"].append(gsm8k_result)
            print(
                f"\nGSM8K Complete: {gsm8k_result['accuracy']:.1f}% accuracy, {gsm8k_result['cost_reduction_pct']:.1f}% cost reduction"
            )
        except Exception as e:
            print(f"GSM8K Error: {e}")
            results["benchmarks"].append({"benchmark": "GSM8K", "error": str(e)})

    if "mmlu" in benchmarks:
        print("\n" + "=" * 80)
        print("Running MMLU Benchmark...")
        print("=" * 80)
        try:
            mmlu_config = BenchmarkConfig.for_mmlu(mode)
            mmlu_result = await run_mmlu_benchmark(mmlu_config, mmlu_samples)
            results["benchmarks"].append(mmlu_result)
            print(
                f"\nMMLU Complete: {mmlu_result['accuracy']:.1f}% accuracy, {mmlu_result['cost_reduction_pct']:.1f}% cost reduction"
            )
        except Exception as e:
            print(f"MMLU Error: {e}")
            results["benchmarks"].append({"benchmark": "MMLU", "error": str(e)})

    if "mtbench" in benchmarks:
        print("\n" + "=" * 80)
        print("Running MT-Bench Benchmark...")
        print("=" * 80)
        try:
            mtbench_config = BenchmarkConfig.for_mtbench(mode)
            mtbench_result = await run_mtbench_benchmark(mtbench_config, mtbench_samples)
            results["benchmarks"].append(mtbench_result)
            print(
                f"\nMT-Bench Complete: {mtbench_result['accuracy']:.1f}% accuracy, {mtbench_result['cost_reduction_pct']:.1f}% cost reduction"
            )
        except Exception as e:
            print(f"MT-Bench Error: {e}")
            results["benchmarks"].append({"benchmark": "MT-Bench", "error": str(e)})

    # Print summary
    print_results_table(results["benchmarks"], DEFAULT_TARGETS)

    # Check targets
    target_checks = check_targets(results, DEFAULT_TARGETS)
    results["target_checks"] = target_checks

    print("\nTarget Check:")
    for benchmark, passed in target_checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {benchmark}: {status}")

    all_passed = all(target_checks.values()) if target_checks else False
    results["all_targets_met"] = all_passed

    if all_passed:
        print("\n🎉 ALL TARGETS MET! Ready for Studio development.")
    else:
        print("\n⚠️  Some targets not met. Tuning needed.")

    results["completed"] = datetime.now().isoformat()

    return results


async def run_comparison(
    benchmarks: Optional[list[str]] = None, quick: bool = False
) -> dict[str, Any]:
    """
    Run all benchmarks in all modes for comparison.

    Args:
        benchmarks: List of benchmarks to run
        quick: If True, use reduced sample sizes

    Returns:
        Comparison results
    """
    print("\n" + "=" * 80)
    print("CASCADEFLOW BENCHMARK COMPARISON")
    print("=" * 80)
    print("\nRunning all benchmarks in all modes for comparison...")

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "modes": {},
    }

    for mode in BenchmarkMode:
        print(f"\n{'='*40}")
        print(f"MODE: {mode.value.upper()}")
        print(f"{'='*40}")

        results = await run_all_benchmarks(mode=mode, benchmarks=benchmarks, quick=quick)
        all_results["modes"][mode.value] = results

    # Generate comparison summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)

    print(f"\n{'Mode':<15} {'GSM8K':<20} {'MMLU':<20} {'MT-Bench':<20}")
    print("-" * 80)

    for mode_name, mode_results in all_results["modes"].items():
        gsm8k_str = "N/A"
        mmlu_str = "N/A"
        mtbench_str = "N/A"

        for bench in mode_results.get("benchmarks", []):
            cost_red = bench.get("cost_reduction_pct", 0)
            accuracy = bench.get("accuracy", 0)
            if bench.get("benchmark") == "GSM8K":
                gsm8k_str = f"{cost_red:.0f}% / {accuracy:.0f}%"
            elif bench.get("benchmark") == "MMLU":
                mmlu_str = f"{cost_red:.0f}% / {accuracy:.0f}%"
            elif bench.get("benchmark") == "MT-Bench":
                mtbench_str = f"{cost_red:.0f}% / {accuracy:.0f}%"

        print(f"{mode_name:<15} {gsm8k_str:<20} {mmlu_str:<20} {mtbench_str:<20}")

    print("-" * 80)
    print("Format: Cost Reduction / Accuracy")

    return all_results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CascadeFlow Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all benchmarks with full configuration
    python run_benchmarks.py

    # Run specific benchmark
    python run_benchmarks.py --benchmark gsm8k

    # Run with baseline mode (no semantic/domain)
    python run_benchmarks.py --mode baseline

    # Run comparison of all modes
    python run_benchmarks.py --compare

    # Quick test with reduced samples
    python run_benchmarks.py --quick
        """,
    )

    parser.add_argument(
        "--benchmark",
        "-b",
        choices=["gsm8k", "mmlu", "mtbench"],
        nargs="+",
        help="Specific benchmark(s) to run",
    )

    parser.add_argument(
        "--mode",
        "-m",
        choices=["baseline", "semantic_only", "domain_only", "full"],
        default="full",
        help="Configuration mode (default: full)",
    )

    parser.add_argument(
        "--compare",
        "-c",
        action="store_true",
        help="Run all benchmarks in all modes for comparison",
    )

    parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="Quick mode with reduced sample sizes",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output file for results (JSON)",
    )

    args = parser.parse_args()

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Run benchmarks
    if args.compare:
        results = asyncio.run(run_comparison(benchmarks=args.benchmark, quick=args.quick))
    else:
        mode = BenchmarkMode(args.mode)
        results = asyncio.run(
            run_all_benchmarks(
                mode=mode,
                benchmarks=args.benchmark,
                quick=args.quick,
            )
        )

    # Save results if output specified
    if args.output:
        save_results(results, args.output)

    # Exit with appropriate code
    if results.get("all_targets_met", False):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
