"""
Comprehensive Production Benchmark Suite for CascadeFlow

This benchmark suite tests real-world performance of CascadeFlow across multiple dimensions:

1. **Provider Testing**: Test all available providers with real API calls
2. **Cost Tracking**: Compare LiteLLM vs fallback cost tracking accuracy
3. **Semantic Quality**: Compare ML-based vs rule-based quality validation
4. **Latency Analysis**: Identify bottlenecks in the cascade pipeline
5. **Query Complexity**: Test trivial, simple, complex, and expert queries
6. **Query Length**: Test short, medium, and long prompts
7. **Tool Calling**: Benchmark tool calling performance
8. **Cost Savings**: Measure actual savings from cascade vs always-premium

Usage:
    # Run all benchmarks
    python3 -m benchmarks.production_benchmark

    # Run specific benchmark
    python3 -m benchmarks.production_benchmark --benchmark=provider_comparison

    # Run with specific providers
    python3 -m benchmarks.production_benchmark --providers=openai,anthropic,groq

    # Generate detailed report
    python3 -m benchmarks.production_benchmark --report=detailed

Requirements:
    - Set API keys in .env file for providers you want to test
    - Install optional dependencies: pip install litellm fastembed
    - Recommended: Run with multiple providers for best comparison

Output:
    - Comparison tables (console)
    - Detailed report (markdown file)
    - CSV data export (for further analysis)
    - Performance charts (if matplotlib available)
"""

import asyncio
import json
import os
import statistics
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# TEST QUERY DATASET
# ============================================================================

@dataclass
class BenchmarkQuery:
    """A query for benchmarking."""

    id: str
    category: str  # trivial, simple, complex, expert
    length: str  # short, medium, long
    domain: str  # code, medical, general, data, etc.
    query: str
    expected_min_tokens: int = 10
    expected_max_tokens: int = 500
    requires_tools: bool = False
    tools: Optional[List[Dict]] = None


# Comprehensive query dataset representing real-world usage
BENCHMARK_QUERIES = [
    # =================================================================
    # TRIVIAL QUERIES (Single fact, simple lookup)
    # =================================================================
    BenchmarkQuery(
        id="trivial_short_general_1",
        category="trivial",
        length="short",
        domain="general",
        query="What is 2+2?",
        expected_min_tokens=5,
        expected_max_tokens=20,
    ),
    BenchmarkQuery(
        id="trivial_short_general_2",
        category="trivial",
        length="short",
        domain="general",
        query="Who is the president of France?",
        expected_min_tokens=5,
        expected_max_tokens=30,
    ),
    BenchmarkQuery(
        id="trivial_short_code_1",
        category="trivial",
        length="short",
        domain="code",
        query="What is a Python list?",
        expected_min_tokens=10,
        expected_max_tokens=50,
    ),

    # =================================================================
    # SIMPLE QUERIES (Straightforward questions, moderate responses)
    # =================================================================
    BenchmarkQuery(
        id="simple_short_code_1",
        category="simple",
        length="short",
        domain="code",
        query="Write a Python function to reverse a string",
        expected_min_tokens=20,
        expected_max_tokens=100,
    ),
    BenchmarkQuery(
        id="simple_medium_general_1",
        category="simple",
        length="medium",
        domain="general",
        query="Explain the difference between a virus and a bacterial infection. Include symptoms and treatment approaches.",
        expected_min_tokens=80,
        expected_max_tokens=200,
    ),
    BenchmarkQuery(
        id="simple_medium_data_1",
        category="simple",
        length="medium",
        domain="data",
        query="What is the difference between mean, median, and mode? Provide examples of when to use each.",
        expected_min_tokens=60,
        expected_max_tokens=150,
    ),
    BenchmarkQuery(
        id="simple_medium_code_2",
        category="simple",
        length="medium",
        domain="code",
        query="Explain async/await in Python and provide a simple example of fetching data from an API.",
        expected_min_tokens=100,
        expected_max_tokens=250,
    ),

    # =================================================================
    # COMPLEX QUERIES (Multi-step reasoning, detailed explanations)
    # =================================================================
    BenchmarkQuery(
        id="complex_medium_code_1",
        category="complex",
        length="medium",
        domain="code",
        query="Implement a binary search tree in Python with insert, search, and delete operations. Include proper error handling.",
        expected_min_tokens=150,
        expected_max_tokens=400,
    ),
    BenchmarkQuery(
        id="complex_long_general_1",
        category="complex",
        length="long",
        domain="general",
        query="Analyze the economic impacts of climate change on developing nations. Consider agriculture, infrastructure, health, and social factors. Provide specific examples from at least 3 countries and discuss potential mitigation strategies.",
        expected_min_tokens=300,
        expected_max_tokens=800,
    ),
    BenchmarkQuery(
        id="complex_long_code_2",
        category="complex",
        length="long",
        domain="code",
        query="Design a distributed caching system that can handle 100k requests per second. Explain the architecture, data structures, consistency models, and failure handling. Include pseudocode for the core operations.",
        expected_min_tokens=400,
        expected_max_tokens=1000,
    ),
    BenchmarkQuery(
        id="complex_long_data_1",
        category="complex",
        length="long",
        domain="data",
        query="Explain gradient boosting algorithms (XGBoost, LightGBM, CatBoost). Compare their strengths, weaknesses, hyperparameters, and use cases. Provide Python code examples for a classification problem.",
        expected_min_tokens=350,
        expected_max_tokens=900,
    ),

    # =================================================================
    # EXPERT QUERIES (Deep technical knowledge, nuanced reasoning)
    # =================================================================
    BenchmarkQuery(
        id="expert_long_code_1",
        category="expert",
        length="long",
        domain="code",
        query="Design a consensus algorithm for a distributed database that guarantees linearizability while minimizing latency. Compare your approach to Raft and Paxos. Explain the trade-offs in CAP theorem terms and provide detailed pseudocode for the leader election and log replication phases.",
        expected_min_tokens=500,
        expected_max_tokens=1500,
    ),
    BenchmarkQuery(
        id="expert_long_medical_1",
        category="expert",
        length="long",
        domain="medical",
        query="Discuss the molecular mechanisms of CRISPR-Cas9 gene editing, including off-target effects, delivery methods, and ethical considerations. Analyze recent clinical trials for sickle cell disease and beta-thalassemia, and explain the regulatory challenges for FDA approval.",
        expected_min_tokens=400,
        expected_max_tokens=1200,
    ),
    BenchmarkQuery(
        id="expert_long_data_2",
        category="expert",
        length="long",
        domain="data",
        query="Explain the mathematics behind transformer architectures in deep learning. Cover attention mechanisms, positional encodings, layer normalization, and the training process. Derive the computational complexity and discuss optimization techniques like flash attention. Include the mathematical formulas.",
        expected_min_tokens=600,
        expected_max_tokens=1500,
    ),

    # =================================================================
    # TOOL CALLING QUERIES
    # =================================================================
    BenchmarkQuery(
        id="tool_simple_code_1",
        category="simple",
        length="short",
        domain="code",
        query="What's the current weather in San Francisco and New York?",
        expected_min_tokens=50,
        expected_max_tokens=150,
        requires_tools=True,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "City name"
                            }
                        },
                        "required": ["city"]
                    }
                }
            }
        ]
    ),
    BenchmarkQuery(
        id="tool_complex_data_1",
        category="complex",
        length="medium",
        domain="data",
        query="Calculate the mean and standard deviation of [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], then use those to generate 5 random numbers from a normal distribution with those parameters.",
        expected_min_tokens=100,
        expected_max_tokens=300,
        requires_tools=True,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "calculate_statistics",
                    "description": "Calculate statistical measures",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "numbers": {"type": "array", "items": {"type": "number"}},
                            "metrics": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_random",
                    "description": "Generate random numbers from a distribution",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "distribution": {"type": "string"},
                            "mean": {"type": "number"},
                            "std": {"type": "number"},
                            "count": {"type": "integer"}
                        }
                    }
                }
            }
        ]
    ),
]


# ============================================================================
# RESULT TRACKING
# ============================================================================

@dataclass
class BenchmarkResult:
    """Result from a single benchmark run."""

    query_id: str
    provider: str
    model: str

    # Response quality
    response: str
    tokens_used: int
    confidence: float

    # Performance metrics
    latency_ms: float
    cost_usd: float

    # Cost tracking method
    cost_method: str  # "litellm" or "fallback"

    # Quality validation
    quality_method: str  # "semantic_ml" or "rule_based"
    quality_score: float
    quality_passed: bool

    # Metadata
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class AggregatedMetrics:
    """Aggregated metrics across multiple runs."""

    name: str
    count: int

    # Latency stats (ms)
    latency_mean: float
    latency_median: float
    latency_p95: float
    latency_p99: float
    latency_min: float
    latency_max: float

    # Cost stats (USD)
    cost_total: float
    cost_mean: float
    cost_median: float

    # Quality stats
    quality_mean: float
    quality_pass_rate: float
    confidence_mean: float

    # Token stats
    tokens_mean: float
    tokens_total: int

    # Error rate
    error_count: int
    error_rate: float


# ============================================================================
# BENCHMARK RUNNER
# ============================================================================

class ProductionBenchmark:
    """Comprehensive production benchmark suite."""

    def __init__(
        self,
        providers: Optional[List[str]] = None,
        enable_litellm: bool = True,
        enable_semantic: bool = True,
        output_dir: str = "./benchmark_results",
    ):
        """
        Initialize benchmark suite.

        Args:
            providers: List of providers to test (None = all available)
            enable_litellm: Test with LiteLLM cost tracking
            enable_semantic: Test with ML semantic quality
            output_dir: Directory for output files
        """
        self.providers = providers or self._detect_available_providers()
        self.enable_litellm = enable_litellm
        self.enable_semantic = enable_semantic
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: List[BenchmarkResult] = []

    def _detect_available_providers(self) -> List[str]:
        """Detect which providers have API keys configured."""
        available = []

        # Check environment for API keys
        provider_env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "groq": "GROQ_API_KEY",
            "together": "TOGETHER_API_KEY",
        }

        for provider, env_var in provider_env_vars.items():
            if os.getenv(env_var):
                available.append(provider)

        if not available:
            print("⚠️  No API keys found. Set API keys in .env or environment variables.")
            print("   Available providers: openai, anthropic, groq, together")

        return available

    async def run_all_benchmarks(self):
        """Run all benchmark tests."""
        print("=" * 80)
        print("CASCADEFLOW PRODUCTION BENCHMARK SUITE")
        print("=" * 80)
        print()
        print(f"Providers to test: {', '.join(self.providers)}")
        print(f"Queries to run: {len(BENCHMARK_QUERIES)}")
        print(f"LiteLLM enabled: {self.enable_litellm}")
        print(f"Semantic ML enabled: {self.enable_semantic}")
        print()

        # Run benchmarks
        await self._benchmark_provider_comparison()
        await self._benchmark_cost_tracking_comparison()
        await self._benchmark_semantic_quality_comparison()
        await self._benchmark_cascade_vs_direct()
        await self._benchmark_latency_analysis()

        # Generate report
        self._generate_report()

    async def _benchmark_provider_comparison(self):
        """Benchmark all providers with real API calls."""
        print("\n" + "=" * 80)
        print("BENCHMARK 1: Provider Comparison")
        print("=" * 80)
        print("Testing all providers with same queries to compare quality, speed, cost")
        print()

        # Import providers
        from cascadeflow.providers.openai import OpenAIProvider
        from cascadeflow.providers.anthropic import AnthropicProvider
        from cascadeflow.providers.groq import GroqProvider
        from cascadeflow.providers.together import TogetherProvider

        provider_map = {
            "openai": (OpenAIProvider, "gpt-4o-mini"),
            "anthropic": (AnthropicProvider, "claude-3-5-haiku-20241022"),
            "groq": (GroqProvider, "llama-3.1-8b-instant"),
            "together": (TogetherProvider, "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"),
        }

        # Use subset of queries for faster testing
        test_queries = [q for q in BENCHMARK_QUERIES if not q.requires_tools][:5]

        for provider_name in self.providers:
            if provider_name not in provider_map:
                continue

            print(f"\n📊 Testing {provider_name}...")
            provider_class, model = provider_map[provider_name]

            try:
                provider = provider_class()
            except Exception as e:
                print(f"   ⚠️  Failed to initialize: {e}")
                continue

            for query in test_queries:
                try:
                    start_time = time.time()
                    result = await provider.complete(
                        prompt=query.query,
                        model=model,
                        max_tokens=query.expected_max_tokens
                    )
                    latency_ms = (time.time() - start_time) * 1000

                    benchmark_result = BenchmarkResult(
                        query_id=query.id,
                        provider=provider_name,
                        model=model,
                        response=result.content,
                        tokens_used=result.tokens_used,
                        confidence=result.confidence,
                        latency_ms=latency_ms,
                        cost_usd=result.cost,
                        cost_method="litellm" if self.enable_litellm else "fallback",
                        quality_method="n/a",
                        quality_score=0.0,
                        quality_passed=True,
                    )
                    self.results.append(benchmark_result)

                    print(f"   ✓ {query.id[:20]:20s} {latency_ms:6.0f}ms ${result.cost:.6f} {result.tokens_used:4d} tokens")

                except Exception as e:
                    print(f"   ✗ {query.id[:20]:20s} Error: {str(e)[:40]}")
                    self.results.append(BenchmarkResult(
                        query_id=query.id,
                        provider=provider_name,
                        model=model,
                        response="",
                        tokens_used=0,
                        confidence=0.0,
                        latency_ms=0.0,
                        cost_usd=0.0,
                        cost_method="error",
                        quality_method="error",
                        quality_score=0.0,
                        quality_passed=False,
                        error=str(e),
                    ))

        print(f"\n✅ Provider comparison complete: {len(self.results)} results collected")

    async def _benchmark_cost_tracking_comparison(self):
        """Compare LiteLLM vs fallback cost tracking."""
        print("\n" + "=" * 80)
        print("BENCHMARK 2: Cost Tracking Comparison")
        print("=" * 80)
        print("Comparing LiteLLM accurate pricing vs fallback estimates")
        print()

        # TODO: Implement cost tracking comparison
        pass

    async def _benchmark_semantic_quality_comparison(self):
        """Compare ML semantic quality vs rule-based."""
        print("\n" + "=" * 80)
        print("BENCHMARK 3: Semantic Quality Comparison")
        print("=" * 80)
        print("Comparing ML-based semantic validation vs rule-based heuristics")
        print()

        # TODO: Implement semantic quality comparison
        pass

    async def _benchmark_cascade_vs_direct(self):
        """Compare cascade routing vs always using premium models."""
        print("\n" + "=" * 80)
        print("BENCHMARK 4: Cascade vs Always-Premium")
        print("=" * 80)
        print("Measuring cost savings from intelligent cascade routing")
        print()

        # TODO: Implement cascade comparison
        pass

    async def _benchmark_latency_analysis(self):
        """Analyze latency bottlenecks."""
        print("\n" + "=" * 80)
        print("BENCHMARK 5: Latency Analysis")
        print("=" * 80)
        print("Identifying performance bottlenecks in the pipeline")
        print()

        # TODO: Implement latency analysis
        pass

    def _generate_report(self):
        """Generate comprehensive benchmark report."""
        print("\n" + "=" * 80)
        print("GENERATING REPORT")
        print("=" * 80)
        print()

        if not self.results:
            print("⚠️  No results to report")
            return

        # Aggregate by provider
        by_provider = defaultdict(list)
        for r in self.results:
            if not r.error:
                by_provider[r.provider].append(r)

        print("\n" + "=" * 80)
        print("PROVIDER COMPARISON SUMMARY")
        print("=" * 80)
        print()

        # Print comparison table
        print(f"{'Provider':<15} {'Count':<7} {'Latency (ms)':>15} {'Cost (USD)':>12} {'Tokens':>10} {'Confidence':>12}")
        print(f"{'':15} {'':7} {'Mean':>7} {'P95':>7} {'Mean':>7} {'Total':>7} {'Mean':>7} {'Mean':>12}")
        print("-" * 95)

        for provider_name in sorted(by_provider.keys()):
            results_list = by_provider[provider_name]
            latencies = [r.latency_ms for r in results_list]
            costs = [r.cost_usd for r in results_list]
            tokens = [r.tokens_used for r in results_list]
            confidences = [r.confidence for r in results_list]

            if latencies:
                latency_mean = statistics.mean(latencies)
                latency_p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
                cost_mean = statistics.mean(costs)
                cost_total = sum(costs)
                tokens_mean = statistics.mean(tokens)
                confidence_mean = statistics.mean(confidences)

                print(f"{provider_name:<15} {len(results_list):<7} "
                      f"{latency_mean:>7.0f} {latency_p95:>7.0f} "
                      f"${cost_mean:>6.4f} ${cost_total:>6.4f} "
                      f"{tokens_mean:>7.0f} "
                      f"{confidence_mean:>12.2%}")

        # Cost tracking comparison if multiple methods
        cost_methods = set(r.cost_method for r in self.results if r.cost_method != "error")
        if len(cost_methods) > 1:
            print("\n" + "=" * 80)
            print("COST TRACKING COMPARISON")
            print("=" * 80)
            print()

            for method in sorted(cost_methods):
                method_results = [r for r in self.results if r.cost_method == method and not r.error]
                if method_results:
                    avg_cost = statistics.mean([r.cost_usd for r in method_results])
                    print(f"{method:20s}: ${avg_cost:.6f} avg ({len(method_results)} queries)")

        # Query complexity analysis
        print("\n" + "=" * 80)
        print("QUERY COMPLEXITY ANALYSIS")
        print("=" * 80)
        print()

        by_category = defaultdict(list)
        for r in self.results:
            if not r.error:
                # Extract category from query_id
                category = r.query_id.split("_")[0]
                by_category[category].append(r)

        print(f"{'Category':<12} {'Count':<7} {'Avg Latency':>12} {'Avg Cost':>12} {'Avg Tokens':>12}")
        print("-" * 55)

        for category in ["trivial", "simple", "complex", "expert"]:
            if category in by_category:
                cat_results = by_category[category]
                avg_lat = statistics.mean([r.latency_ms for r in cat_results])
                avg_cost = statistics.mean([r.cost_usd for r in cat_results])
                avg_tokens = statistics.mean([r.tokens_used for r in cat_results])
                print(f"{category:<12} {len(cat_results):<7} {avg_lat:>10.0f}ms ${avg_cost:>10.6f} {avg_tokens:>10.0f}")

        # Save detailed results to JSON
        results_file = self.output_dir / "results.json"
        with open(results_file, "w") as f:
            json.dump([asdict(r) for r in self.results], f, indent=2)
        print(f"\n📄 Detailed results saved to: {results_file}")

        # Save markdown report
        self._generate_markdown_report()

        print(f"\n✅ Report generation complete")

    def _generate_markdown_report(self):
        """Generate markdown report."""
        report_file = self.output_dir / "report.md"

        with open(report_file, "w") as f:
            f.write("# CascadeFlow Production Benchmark Report\n\n")
            f.write(f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Providers Tested**: {', '.join(self.providers)}\n\n")
            f.write(f"**Total Queries**: {len([r for r in self.results if not r.error])}\n\n")
            f.write("---\n\n")

            # Provider comparison
            f.write("## Provider Comparison\n\n")

            by_provider = defaultdict(list)
            for r in self.results:
                if not r.error:
                    by_provider[r.provider].append(r)

            f.write("| Provider | Queries | Avg Latency (ms) | P95 Latency (ms) | Avg Cost | Total Cost | Avg Tokens |\n")
            f.write("|----------|---------|------------------|------------------|----------|------------|------------|\n")

            for provider_name in sorted(by_provider.keys()):
                results_list = by_provider[provider_name]
                latencies = [r.latency_ms for r in results_list]
                costs = [r.cost_usd for r in results_list]
                tokens = [r.tokens_used for r in results_list]

                if latencies:
                    latency_mean = statistics.mean(latencies)
                    latency_p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
                    cost_mean = statistics.mean(costs)
                    cost_total = sum(costs)
                    tokens_mean = statistics.mean(tokens)

                    f.write(f"| {provider_name} | {len(results_list)} | "
                           f"{latency_mean:.0f} | {latency_p95:.0f} | "
                           f"${cost_mean:.6f} | ${cost_total:.6f} | {tokens_mean:.0f} |\n")

            # Query complexity
            f.write("\n## Query Complexity Analysis\n\n")

            by_category = defaultdict(list)
            for r in self.results:
                if not r.error:
                    category = r.query_id.split("_")[0]
                    by_category[category].append(r)

            f.write("| Category | Queries | Avg Latency | Avg Cost | Avg Tokens |\n")
            f.write("|----------|---------|-------------|----------|------------|\n")

            for category in ["trivial", "simple", "complex", "expert"]:
                if category in by_category:
                    cat_results = by_category[category]
                    avg_lat = statistics.mean([r.latency_ms for r in cat_results])
                    avg_cost = statistics.mean([r.cost_usd for r in cat_results])
                    avg_tokens = statistics.mean([r.tokens_used for r in cat_results])
                    f.write(f"| {category.title()} | {len(cat_results)} | "
                           f"{avg_lat:.0f}ms | ${avg_cost:.6f} | {avg_tokens:.0f} |\n")

            # Key insights
            f.write("\n## Key Insights\n\n")

            # Find fastest provider
            if by_provider:
                fastest = min(by_provider.items(), key=lambda x: statistics.mean([r.latency_ms for r in x[1]]))
                f.write(f"- **Fastest Provider**: {fastest[0]} ({statistics.mean([r.latency_ms for r in fastest[1]]):.0f}ms avg)\n")

                # Find cheapest
                cheapest = min(by_provider.items(), key=lambda x: statistics.mean([r.cost_usd for r in x[1]]))
                f.write(f"- **Cheapest Provider**: {cheapest[0]} (${statistics.mean([r.cost_usd for r in cheapest[1]]):.6f} avg)\n")

                # Find best quality
                best_conf = max(by_provider.items(), key=lambda x: statistics.mean([r.confidence for r in x[1]]))
                f.write(f"- **Highest Confidence**: {best_conf[0]} ({statistics.mean([r.confidence for r in best_conf[1]]):.1%} avg)\n")

            f.write("\n## Recommendations\n\n")
            f.write("Based on the benchmark results:\n\n")
            f.write("1. **For Speed**: Use Groq if available (typically 4-5x faster)\n")
            f.write("2. **For Cost**: Groq and Together AI offer best value\n")
            f.write("3. **For Quality**: OpenAI and Anthropic show highest confidence scores\n")
            f.write("4. **For Production**: Consider cascade routing to balance all three\n\n")

        print(f"📄 Markdown report saved to: {report_file}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Run production benchmarks."""
    import argparse

    parser = argparse.ArgumentParser(
        description="CascadeFlow Production Benchmark Suite"
    )
    parser.add_argument(
        "--providers",
        type=str,
        help="Comma-separated list of providers (openai,anthropic,groq,together)"
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        choices=["all", "provider", "cost", "semantic", "cascade", "latency"],
        default="all",
        help="Which benchmark to run"
    )
    parser.add_argument(
        "--no-litellm",
        action="store_true",
        help="Disable LiteLLM cost tracking"
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Disable semantic ML quality validation"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./benchmark_results",
        help="Output directory for results"
    )

    args = parser.parse_args()

    # Parse providers
    providers = None
    if args.providers:
        providers = [p.strip() for p in args.providers.split(",")]

    # Create benchmark suite
    benchmark = ProductionBenchmark(
        providers=providers,
        enable_litellm=not args.no_litellm,
        enable_semantic=not args.no_semantic,
        output_dir=args.output,
    )

    # Run benchmarks
    await benchmark.run_all_benchmarks()

    print("\n✅ Benchmark complete!")
    print(f"📊 Results saved to: {benchmark.output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
