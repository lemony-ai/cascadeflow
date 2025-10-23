"""
Comprehensive performance analysis for MVP cascade - Cost & Speed Analytics Edition

Deep analysis with detailed metrics:
- 100+ queries across 4 complexity levels
- 6 providers (OpenAI, Anthropic, Groq, Together, Ollama)
- Detailed cost tracking and savings analysis
- Speed comparison vs baseline (verifier-only)
- Beautiful summary tables
"""

import os
import statistics
from dataclasses import dataclass, field

import pytest
from cascadeflow.config import ModelConfig
from cascadeflow.speculative import WholeResponseCascade

from cascadeflow.quality import QualityConfig

# Load .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed


@dataclass
class QueryResult:
    """Detailed result tracking for analytics."""

    query: str
    complexity: str
    draft_accepted: bool
    cascade_cost: float
    baseline_cost: float
    cost_saved: float
    cascade_latency_ms: float
    baseline_latency_ms: float
    speedup: float
    drafter_model: str
    verifier_model: str


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""

    total_queries: int = 0
    drafts_accepted: int = 0
    drafts_rejected: int = 0

    # Cost metrics
    total_cascade_cost: float = 0.0
    total_baseline_cost: float = 0.0
    total_cost_saved: float = 0.0

    # Speed metrics
    total_cascade_latency: float = 0.0
    total_baseline_latency: float = 0.0

    # Per-complexity tracking
    by_complexity: dict[str, list[QueryResult]] = field(default_factory=dict)

    def add_result(self, result: QueryResult):
        """Add a query result to metrics."""
        self.total_queries += 1
        if result.draft_accepted:
            self.drafts_accepted += 1
        else:
            self.drafts_rejected += 1

        self.total_cascade_cost += result.cascade_cost
        self.total_baseline_cost += result.baseline_cost
        self.total_cost_saved += result.cost_saved
        self.total_cascade_latency += result.cascade_latency_ms
        self.total_baseline_latency += result.baseline_latency_ms

        if result.complexity not in self.by_complexity:
            self.by_complexity[result.complexity] = []
        self.by_complexity[result.complexity].append(result)


# Test configurations
@pytest.fixture
def test_models():
    """Get test model configurations for all providers."""
    return {
        "openai_cheap": ModelConfig(
            name="gpt-3.5-turbo",
            provider="openai",
            cost=0.002,
            speed_ms=800,
            quality_score=0.75,
            domains=["general"],
        ),
        "openai_expensive": ModelConfig(
            name="gpt-4",
            provider="openai",
            cost=0.03,
            speed_ms=2000,
            quality_score=0.95,
            domains=["general"],
        ),
        "anthropic_cheap": ModelConfig(
            name="claude-3-haiku-20240307",
            provider="anthropic",
            cost=0.00025,
            speed_ms=600,
            quality_score=0.70,
            domains=["general"],
        ),
        "anthropic_expensive": ModelConfig(
            name="claude-3-sonnet-20240229",
            provider="anthropic",
            cost=0.003,
            speed_ms=1500,
            quality_score=0.90,
            domains=["general"],
        ),
        "groq_cheap": ModelConfig(
            name="llama-3.1-8b-instant",
            provider="groq",
            cost=0.00005,
            speed_ms=300,
            quality_score=0.72,
            domains=["general"],
        ),
        "groq_mid": ModelConfig(
            name="llama-3.1-70b-versatile",
            provider="groq",
            cost=0.00059,
            speed_ms=800,
            quality_score=0.85,
            domains=["general"],
        ),
        "together_cheap": ModelConfig(
            name="meta-llama/Llama-3-8b-chat-hf",
            provider="together",
            cost=0.0002,
            speed_ms=500,
            quality_score=0.70,
            domains=["general"],
        ),
        "together_mid": ModelConfig(
            name="meta-llama/Llama-3-70b-chat-hf",
            provider="together",
            cost=0.0009,
            speed_ms=1200,
            quality_score=0.85,
            domains=["general"],
        ),
        "ollama_local": ModelConfig(
            name="gemma2:2b",
            provider="ollama",
            cost=0.0,
            speed_ms=400,
            quality_score=0.65,
            domains=["general"],
        ),
    }


@pytest.fixture
def providers():
    """Initialize all available providers."""
    from cascadeflow.providers import PROVIDER_REGISTRY

    providers = {}

    if os.getenv("OPENAI_API_KEY"):
        providers["openai"] = PROVIDER_REGISTRY["openai"]()

    if os.getenv("ANTHROPIC_API_KEY"):
        providers["anthropic"] = PROVIDER_REGISTRY["anthropic"]()

    if os.getenv("GROQ_API_KEY"):
        providers["groq"] = PROVIDER_REGISTRY["groq"]()

    if os.getenv("TOGETHER_API_KEY"):
        providers["together"] = PROVIDER_REGISTRY["together"]()

    try:
        providers["ollama"] = PROVIDER_REGISTRY["ollama"]()
    except:
        pass

    return providers


# Extended query sets
QUERY_SETS = {
    "trivial": [
        "What is 2+2?",
        "What is 5*5?",
        "What is 10-3?",
        "What is 8/2?",
        "Is 10 bigger than 5?",
        "What is 3+7?",
        "What is 6*4?",
        "What color is the sky?",
        "Is water wet?",
        "Name one color",
        "How many days in a week?",
        "How many months in a year?",
        "What comes after Monday?",
        "Is fire hot?",
        "Can fish swim?",
        "Do birds fly?",
        "Is ice cold?",
        "Name a fruit",
        "Name an animal",
        "What sound does a dog make?",
    ],
    "simple": [
        "What is Python?",
        "What is JavaScript?",
        "What is HTML?",
        "What is CSS?",
        "What is a variable?",
        "What is a function?",
        "What is a loop?",
        "What is an array?",
        "What is Git?",
        "Who wrote Romeo and Juliet?",
        "What is the capital of France?",
        "What is the capital of Japan?",
        "Who invented the telephone?",
        "What is photosynthesis?",
        "What is gravity?",
        "What is DNA?",
        "What is the internet?",
        "What is democracy?",
        "What is economics?",
        "Who was Albert Einstein?",
    ],
    "medium": [
        "Explain how photosynthesis works",
        "What are the main causes of climate change?",
        "Describe the difference between RAM and ROM",
        "How does a car engine work?",
        "What is machine learning?",
        "Explain the water cycle",
        "How do vaccines work?",
        "What is quantum mechanics?",
        "Explain blockchain technology",
        "How does the human brain process information?",
        "What is the difference between AI and ML?",
        "Explain how the internet works",
        "What causes earthquakes?",
        "How do batteries work?",
        "Explain the theory of evolution",
    ],
    "complex": [
        "Explain quantum entanglement and its implications",
        "Analyze the economic impact of automation on employment",
        "Compare and contrast different political systems",
        "Explain Gödel's incompleteness theorems",
        "Discuss the philosophical implications of consciousness",
        "Analyze the relationship between language and thought",
        "Explain the paradoxes of time travel in physics",
        "Discuss the ethics of artificial intelligence",
        "Analyze the causes and effects of income inequality",
        "Explain the relationship between free will and determinism",
    ],
}


async def run_baseline_query(
    providers, verifier: ModelConfig, query: str, max_tokens: int
) -> tuple[float, float]:
    """Run baseline (verifier-only) for comparison."""
    import time

    provider = providers[verifier.provider]
    start_time = time.time()

    result = await provider.complete(
        model=verifier.name, prompt=query, max_tokens=max_tokens, temperature=0.7
    )

    latency_ms = (time.time() - start_time) * 1000

    # Convert to dict if needed
    if hasattr(result, "to_dict"):
        result_dict = result.to_dict()
    else:
        result_dict = result

    tokens_used = result_dict.get("tokens_used", max_tokens)
    cost = verifier.cost * (tokens_used / 1000)

    return cost, latency_ms


def print_table_header(title: str):
    """Print a nice table header."""
    print("\n" + "=" * 100)
    print(title.center(100))
    print("=" * 100)


def print_cost_savings_table(metrics: PerformanceMetrics):
    """Print detailed cost savings table."""
    print_table_header("COST ANALYSIS")

    print(f"\n{'Metric':<40} {'Value':>15} {'Details':>40}")
    print("-" * 100)

    total_saved = metrics.total_baseline_cost - metrics.total_cascade_cost
    savings_pct = (
        (total_saved / metrics.total_baseline_cost * 100) if metrics.total_baseline_cost > 0 else 0
    )

    print(f"{'Total Queries Processed':<40} {metrics.total_queries:>15d}")
    print(
        f"{'Drafts Accepted':<40} {metrics.drafts_accepted:>15d} {f'({metrics.drafts_accepted/metrics.total_queries*100:.1f}%)':>40}"
    )
    print(
        f"{'Drafts Rejected':<40} {metrics.drafts_rejected:>15d} {f'({metrics.drafts_rejected/metrics.total_queries*100:.1f}%)':>40}"
    )
    print("-" * 100)
    print(f"{'Baseline Cost (Verifier Only)':<40} ${metrics.total_baseline_cost:>14.6f}")
    print(f"{'Actual Cascade Cost':<40} ${metrics.total_cascade_cost:>14.6f}")
    print(f"{'Total Cost Saved':<40} ${total_saved:>14.6f} {f'({savings_pct:.1f}% reduction)':>40}")
    print(
        f"{'Average Cost Per Query (Cascade)':<40} ${metrics.total_cascade_cost/metrics.total_queries:>14.6f}"
    )
    print(
        f"{'Average Cost Per Query (Baseline)':<40} ${metrics.total_baseline_cost/metrics.total_queries:>14.6f}"
    )

    # Cost breakdown by acceptance
    if metrics.drafts_accepted > 0:
        accepted_results = [
            r for results in metrics.by_complexity.values() for r in results if r.draft_accepted
        ]
        avg_cost_accepted = sum(r.cascade_cost for r in accepted_results) / len(accepted_results)
        avg_saved_accepted = sum(r.cost_saved for r in accepted_results) / len(accepted_results)
        print("-" * 100)
        print(
            f"{'Avg Cost When Draft Accepted':<40} ${avg_cost_accepted:>14.6f} {f'(saved ${avg_saved_accepted:.6f})':>40}"
        )

    if metrics.drafts_rejected > 0:
        rejected_results = [
            r for results in metrics.by_complexity.values() for r in results if not r.draft_accepted
        ]
        avg_cost_rejected = sum(r.cascade_cost for r in rejected_results) / len(rejected_results)
        avg_wasted_rejected = sum(-r.cost_saved for r in rejected_results) / len(rejected_results)
        print(
            f"{'Avg Cost When Draft Rejected':<40} ${avg_cost_rejected:>14.6f} {f'(wasted ${avg_wasted_rejected:.6f})':>40}"
        )


def print_speed_performance_table(metrics: PerformanceMetrics):
    """Print detailed speed performance table."""
    print_table_header("SPEED ANALYSIS")

    print(f"\n{'Metric':<40} {'Value':>15} {'vs Baseline':>40}")
    print("-" * 100)

    avg_cascade_latency = metrics.total_cascade_latency / metrics.total_queries
    avg_baseline_latency = metrics.total_baseline_latency / metrics.total_queries
    overall_speedup = avg_baseline_latency / avg_cascade_latency if avg_cascade_latency > 0 else 1.0
    time_saved = avg_baseline_latency - avg_cascade_latency

    print(f"{'Baseline Latency (Verifier Only)':<40} {avg_baseline_latency:>14.0f}ms")
    print(
        f"{'Actual Cascade Latency':<40} {avg_cascade_latency:>14.0f}ms {f'({time_saved:.0f}ms faster)':>40}"
    )
    print(f"{'Overall Speedup':<40} {overall_speedup:>14.2f}x")

    # Speed breakdown by acceptance
    accepted_results = [
        r for results in metrics.by_complexity.values() for r in results if r.draft_accepted
    ]
    rejected_results = [
        r for results in metrics.by_complexity.values() for r in results if not r.draft_accepted
    ]

    if accepted_results:
        avg_speedup_accepted = statistics.mean(r.speedup for r in accepted_results)
        avg_latency_accepted = statistics.mean(r.cascade_latency_ms for r in accepted_results)
        print("-" * 100)
        print(
            f"{'Avg Speedup When Draft Accepted':<40} {avg_speedup_accepted:>14.2f}x {f'({avg_latency_accepted:.0f}ms)':>40}"
        )

    if rejected_results:
        avg_speedup_rejected = statistics.mean(r.speedup for r in rejected_results)
        avg_latency_rejected = statistics.mean(r.cascade_latency_ms for r in rejected_results)
        print(
            f"{'Avg Speedup When Draft Rejected':<40} {avg_speedup_rejected:>14.2f}x {f'({avg_latency_rejected:.0f}ms)':>40}"
        )


def print_complexity_breakdown_table(metrics: PerformanceMetrics):
    """Print breakdown by query complexity."""
    print_table_header("PERFORMANCE BY QUERY COMPLEXITY")

    print(
        f"\n{'Complexity':<12} {'Queries':>8} {'Accept%':>8} {'Avg Cost':>12} {'Cost Saved':>12} {'Speedup':>10} {'Latency':>10}"
    )
    print("-" * 100)

    for complexity in ["trivial", "simple", "medium", "complex"]:
        if complexity not in metrics.by_complexity:
            continue

        results = metrics.by_complexity[complexity]
        n = len(results)
        accept_rate = sum(1 for r in results if r.draft_accepted) / n * 100
        avg_cost = sum(r.cascade_cost for r in results) / n
        avg_saved = sum(r.cost_saved for r in results) / n
        avg_speedup = statistics.mean(r.speedup for r in results)
        avg_latency = statistics.mean(r.cascade_latency_ms for r in results)

        print(
            f"{complexity.capitalize():<12} {n:>8d} {accept_rate:>7.1f}% "
            f"${avg_cost:>11.6f} ${avg_saved:>11.6f} {avg_speedup:>9.2f}x {avg_latency:>9.0f}ms"
        )


def print_final_recommendation(metrics: PerformanceMetrics):
    """Print final recommendation."""
    print_table_header("PRODUCTION READINESS ASSESSMENT")

    acceptance_rate = metrics.drafts_accepted / metrics.total_queries
    total_saved = metrics.total_baseline_cost - metrics.total_cascade_cost
    savings_pct = (
        (total_saved / metrics.total_baseline_cost * 100) if metrics.total_baseline_cost > 0 else 0
    )
    avg_cascade_latency = metrics.total_cascade_latency / metrics.total_queries
    avg_baseline_latency = metrics.total_baseline_latency / metrics.total_queries
    overall_speedup = avg_baseline_latency / avg_cascade_latency if avg_cascade_latency > 0 else 1.0

    checks = {
        "Acceptance rate 40-70%": (0.40 <= acceptance_rate <= 0.70, f"{acceptance_rate:.1%}"),
        "Cost savings >= 20%": (savings_pct >= 20, f"{savings_pct:.1f}%"),
        "Overall speedup >= 1.5x": (overall_speedup >= 1.5, f"{overall_speedup:.2f}x"),
        "No negative cost impact": (total_saved >= 0, f"${total_saved:.6f}"),
        "Sample size >= 20": (metrics.total_queries >= 20, f"{metrics.total_queries}"),
    }

    print(f"\n{'Check':<35} {'Status':>10} {'Value':>20}")
    print("-" * 100)

    for check, (passed, value) in checks.items():
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {check:<33} {status:>10} {value:>20}")

    all_passed = all(passed for passed, _ in checks.values())

    print("\n" + "=" * 100)
    if all_passed:
        print("VERDICT: PRODUCTION READY".center(100))
        print("\nThe cascade demonstrates:")
        print(f"  • {savings_pct:.1f}% cost reduction compared to verifier-only")
        print(f"  • {overall_speedup:.2f}x average speedup")
        print(f"  • {acceptance_rate:.1%} acceptance rate (balanced)")
        print("\nRecommendation: Deploy to production with confidence.")
    else:
        print("VERDICT: NEEDS TUNING".center(100))
        print("\nConsider:")
        failed = [check for check, (passed, _) in checks.items() if not passed]
        for check in failed:
            print(f"  • Adjust settings for: {check}")
    print("=" * 100)


@pytest.mark.asyncio
async def test_comprehensive_cost_speed_analysis(test_models, providers):
    """Comprehensive cost and speed analysis across all query types."""
    if "openai" not in providers:
        pytest.skip("OpenAI API key not available")

    drafter = test_models["openai_cheap"]
    verifier = test_models["openai_expensive"]

    config = QualityConfig.for_production()
    metrics = PerformanceMetrics()

    print("\n" + "=" * 100)
    print("COMPREHENSIVE CASCADE PERFORMANCE ANALYSIS".center(100))
    print("=" * 100)
    print(f"\nDrafter:  {drafter.name} (${drafter.cost:.6f}/1K tokens, ~{drafter.speed_ms}ms)")
    print(f"Verifier: {verifier.name} (${verifier.cost:.6f}/1K tokens, ~{verifier.speed_ms}ms)")
    print("Config:   Production (complexity-aware thresholds)")

    # Test queries from each complexity level
    for complexity, queries in QUERY_SETS.items():
        print(f"\n{'-'*100}")
        print(f"Testing {complexity.upper()} queries ({len(queries[:10])} samples)...")
        print(f"{'-'*100}")

        max_tokens = 30 if complexity == "trivial" else (50 if complexity == "simple" else 80)

        for i, query in enumerate(queries[:10], 1):
            # Run cascade
            cascade = WholeResponseCascade(
                drafter=drafter,
                verifier=verifier,
                providers=providers,
                quality_config=config,
                verbose=False,
            )

            cascade_result = await cascade.execute(
                query=query, max_tokens=max_tokens, temperature=0.7
            )

            # Run baseline for comparison
            baseline_cost, baseline_latency = await run_baseline_query(
                providers, verifier, query, max_tokens
            )

            # Calculate metrics
            cost_saved = baseline_cost - cascade_result.total_cost

            result = QueryResult(
                query=query,
                complexity=complexity,
                draft_accepted=cascade_result.draft_accepted,
                cascade_cost=cascade_result.total_cost,
                baseline_cost=baseline_cost,
                cost_saved=cost_saved,
                cascade_latency_ms=cascade_result.latency_ms,
                baseline_latency_ms=baseline_latency,
                speedup=(
                    baseline_latency / cascade_result.latency_ms
                    if cascade_result.latency_ms > 0
                    else 1.0
                ),
                drafter_model=drafter.name,
                verifier_model=verifier.name,
            )

            metrics.add_result(result)

            # Print progress
            status = "✓" if result.draft_accepted else "✗"
            saved_str = f"+${cost_saved:.6f}" if cost_saved > 0 else f"-${-cost_saved:.6f}"
            print(f"{i:2d}. {status} {query[:50]:52s} | {saved_str:>12} | {result.speedup:.2f}x")

    # Print comprehensive tables
    print_cost_savings_table(metrics)
    print_speed_performance_table(metrics)
    print_complexity_breakdown_table(metrics)
    print_final_recommendation(metrics)

    # Assertions
    assert metrics.total_queries >= 20, "Should test sufficient queries"
    assert metrics.total_cost_saved >= 0, "Should not lose money overall"


@pytest.mark.asyncio
async def test_provider_comparison_matrix(test_models, providers):
    """Compare cost/speed across different provider combinations."""

    # Build provider combinations
    combos = []
    if "groq" in providers and "openai" in providers:
        combos.append(("groq_cheap", "openai_expensive", "Groq → GPT-4"))
    if "anthropic" in providers and "openai" in providers:
        combos.append(("anthropic_cheap", "openai_expensive", "Haiku → GPT-4"))
    if "openai" in providers:
        combos.append(("openai_cheap", "openai_expensive", "GPT-3.5 → GPT-4"))
    if "together" in providers and "openai" in providers:
        combos.append(("together_cheap", "openai_expensive", "Together → GPT-4"))

    if not combos:
        pytest.skip("Need multiple providers")

    print_table_header("PROVIDER COMBINATION COMPARISON")

    test_queries = QUERY_SETS["simple"][:5]

    print(
        f"\n{'Combination':<25} {'Accept%':>8} {'Avg Cost':>12} {'Saved':>12} {'Speedup':>10} {'Latency':>10}"
    )
    print("-" * 100)

    for drafter_key, verifier_key, label in combos:
        drafter = test_models[drafter_key]
        verifier = test_models[verifier_key]

        results = []

        for query in test_queries:
            cascade = WholeResponseCascade(
                drafter=drafter,
                verifier=verifier,
                providers=providers,
                quality_config=QualityConfig.for_production(),
                verbose=False,
            )

            result = await cascade.execute(query=query, max_tokens=50, temperature=0.7)
            baseline_cost, baseline_latency = await run_baseline_query(
                providers, verifier, query, 50
            )

            results.append(
                {
                    "accepted": result.draft_accepted,
                    "cost": result.total_cost,
                    "saved": baseline_cost - result.total_cost,
                    "speedup": baseline_latency / result.latency_ms,
                    "latency": result.latency_ms,
                }
            )

        accept_rate = sum(1 for r in results if r["accepted"]) / len(results) * 100
        avg_cost = statistics.mean(r["cost"] for r in results)
        avg_saved = statistics.mean(r["saved"] for r in results)
        avg_speedup = statistics.mean(r["speedup"] for r in results)
        avg_latency = statistics.mean(r["latency"] for r in results)

        print(
            f"{label:<25} {accept_rate:>7.1f}% ${avg_cost:>11.6f} ${avg_saved:>11.6f} {avg_speedup:>9.2f}x {avg_latency:>9.0f}ms"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
