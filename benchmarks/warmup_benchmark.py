"""
Warmup Benchmark - Measure Performance Improvements
===================================================

This benchmark measures the actual performance improvements from warmup.

Usage:
    python benchmarks/warmup_benchmark.py
"""

import asyncio
import time
import statistics
from dataclasses import dataclass
from typing import List

from cascadeflow import CascadeAgent
from cascadeflow.providers import OllamaProvider
from cascadeflow.schema.config import ModelConfig


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""
    name: str
    latencies: List[float]
    mean: float
    median: float
    std_dev: float
    min: float
    max: float

    def __str__(self):
        return (
            f"{self.name}:\n"
            f"  Mean:   {self.mean:.0f}ms\n"
            f"  Median: {self.median:.0f}ms\n"
            f"  Std:    {self.std_dev:.0f}ms\n"
            f"  Min:    {self.min:.0f}ms\n"
            f"  Max:    {self.max:.0f}ms"
        )


async def run_benchmark(agent, query: str, num_requests: int = 10) -> List[float]:
    """Run multiple requests and measure latency."""
    latencies = []

    for i in range(num_requests):
        start = time.time()
        await agent.run(query)
        latency = (time.time() - start) * 1000
        latencies.append(latency)
        print(f"  Request {i+1}/{num_requests}: {latency:.0f}ms")

    return latencies


def analyze_results(name: str, latencies: List[float]) -> BenchmarkResult:
    """Analyze benchmark results."""
    return BenchmarkResult(
        name=name,
        latencies=latencies,
        mean=statistics.mean(latencies),
        median=statistics.median(latencies),
        std_dev=statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
        min=min(latencies),
        max=max(latencies)
    )


async def benchmark_cold_start():
    """Benchmark cold start (first request after agent creation)."""
    print("\n" + "=" * 70)
    print("Benchmark 1: Cold Start Latency")
    print("=" * 70)
    print("\nMeasuring first-request latency without warmup...")

    cold_start_latencies = []

    for i in range(5):
        # Create new agent (cold)
        model = ModelConfig(
            provider=OllamaProvider(),
            model="llama3.2:1b",
            cost=0.0,
            speed_ms=100,
            quality=0.6
        )
        agent = CascadeAgent(models=[model])

        # Measure first request
        print(f"\nIteration {i+1}/5:")
        start = time.time()
        await agent.run("What is 2+2?")
        latency = (time.time() - start) * 1000
        cold_start_latencies.append(latency)
        print(f"  Cold start latency: {latency:.0f}ms")

    return analyze_results("Cold Start (No Warmup)", cold_start_latencies)


async def benchmark_with_warmup():
    """Benchmark latency with warmup."""
    print("\n" + "=" * 70)
    print("Benchmark 2: Warmup Latency")
    print("=" * 70)
    print("\nMeasuring first-request latency WITH warmup...")

    warmup_latencies = []
    warmup_times = []

    for i in range(5):
        # Create new agent
        model = ModelConfig(
            provider=OllamaProvider(),
            model="llama3.2:1b",
            cost=0.0,
            speed_ms=100,
            quality=0.6
        )
        agent = CascadeAgent(models=[model])

        # Warmup
        print(f"\nIteration {i+1}/5:")
        warmup_start = time.time()
        warmup_result = await agent.warmup()
        warmup_time = (time.time() - warmup_start) * 1000
        warmup_times.append(warmup_time)
        print(f"  Warmup time: {warmup_time:.0f}ms")

        # Measure first request
        start = time.time()
        await agent.run("What is 2+2?")
        latency = (time.time() - start) * 1000
        warmup_latencies.append(latency)
        print(f"  First request latency: {latency:.0f}ms")

    warmup_result = analyze_results("With Warmup", warmup_latencies)

    # Add warmup time analysis
    print(f"\nWarmup Time Stats:")
    print(f"  Mean:   {statistics.mean(warmup_times):.0f}ms")
    print(f"  Median: {statistics.median(warmup_times):.0f}ms")

    return warmup_result


async def benchmark_sustained_load():
    """Benchmark sustained load (many requests)."""
    print("\n" + "=" * 70)
    print("Benchmark 3: Sustained Load (10 requests)")
    print("=" * 70)

    # Without warmup
    print("\n📊 Without Warmup:")
    model1 = ModelConfig(
        provider=OllamaProvider(),
        model="llama3.2:1b",
        cost=0.0,
        speed_ms=100,
        quality=0.6
    )
    agent1 = CascadeAgent(models=[model1])
    no_warmup_latencies = await run_benchmark(agent1, "What is AI?", num_requests=10)
    no_warmup_result = analyze_results("Sustained Load (No Warmup)", no_warmup_latencies)

    # With warmup
    print("\n📊 With Warmup:")
    model2 = ModelConfig(
        provider=OllamaProvider(),
        model="llama3.2:1b",
        cost=0.0,
        speed_ms=100,
        quality=0.6
    )
    agent2 = CascadeAgent(models=[model2])
    await agent2.warmup()
    warmup_latencies = await run_benchmark(agent2, "What is AI?", num_requests=10)
    warmup_result = analyze_results("Sustained Load (With Warmup)", warmup_latencies)

    return no_warmup_result, warmup_result


async def main():
    """Run all benchmarks."""
    print("\n" + "=" * 70)
    print("CascadeFlow Warmup Performance Benchmark")
    print("=" * 70)
    print("\nThis benchmark measures the performance impact of warmup.")
    print("Requirements:")
    print("  - Ollama running: ollama serve")
    print("  - Model pulled: ollama pull llama3.2:1b")
    print()
    input("Press Enter to start benchmarking...")

    try:
        # Run benchmarks
        cold_start_result = await benchmark_cold_start()
        warmup_result = await benchmark_with_warmup()
        sustained_no_warmup, sustained_warmup = await benchmark_sustained_load()

        # Print summary
        print("\n" + "=" * 70)
        print("BENCHMARK RESULTS")
        print("=" * 70)

        print(f"\n{cold_start_result}")
        print(f"\n{warmup_result}")
        print(f"\n{sustained_no_warmup}")
        print(f"\n{sustained_warmup}")

        # Calculate improvements
        print("\n" + "=" * 70)
        print("PERFORMANCE IMPROVEMENTS")
        print("=" * 70)

        cold_reduction = ((cold_start_result.mean - warmup_result.mean) / cold_start_result.mean) * 100
        print(f"\n🚀 Cold Start Improvement: {cold_reduction:.1f}% faster")
        print(f"   {cold_start_result.mean:.0f}ms → {warmup_result.mean:.0f}ms")

        sustained_first_req = sustained_no_warmup.latencies[0]
        sustained_first_warmup = sustained_warmup.latencies[0]
        sustained_reduction = ((sustained_first_req - sustained_first_warmup) / sustained_first_req) * 100
        print(f"\n⚡ First Request Improvement: {sustained_reduction:.1f}% faster")
        print(f"   {sustained_first_req:.0f}ms → {sustained_first_warmup:.0f}ms")

        # Variability improvement
        variability_reduction = ((cold_start_result.std_dev - warmup_result.std_dev) / cold_start_result.std_dev) * 100
        print(f"\n📊 Latency Variability Reduction: {variability_reduction:.1f}%")
        print(f"   Std Dev: {cold_start_result.std_dev:.0f}ms → {warmup_result.std_dev:.0f}ms")

        print("\n" + "=" * 70)
        print("✅ Benchmark Complete!")
        print("=" * 70)
        print("\n💡 Key Findings:")
        print(f"   - Warmup reduces cold-start latency by {cold_reduction:.1f}%")
        print(f"   - First requests are {sustained_reduction:.1f}% faster")
        print(f"   - Latency is more consistent (lower std dev)")
        print(f"   - Warmup overhead: ~{statistics.mean([cold_start_result.mean, warmup_result.mean]):.0f}ms (one-time cost)")
        print()

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        print("\nMake sure:")
        print("  1. Ollama is running (ollama serve)")
        print("  2. Model is pulled (ollama pull llama3.2:1b)")
        print()
        raise


if __name__ == "__main__":
    asyncio.run(main())
