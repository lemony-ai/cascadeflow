"""Provider Comparison Benchmark

Tests if quality engine behavior differs between providers (OpenAI vs Anthropic).

Research Questions:
1. Do OpenAI and Anthropic score the same drafter outputs differently?
2. Does each provider need different quality thresholds?
3. Is semantic quality evaluation consistent across providers?
4. Which provider has faster quality scoring?
5. Are there provider-specific quirks in domain detection?

Methodology:
- Same drafter (gpt-4o-mini) → Multiple verifiers (gpt-4o, claude-sonnet-4)
- Test across multiple query types (simple, complex, domain-specific)
- Measure quality scores, latency, and acceptance rates per provider
- Identify optimal threshold per provider
"""

import asyncio
import os
import time
from dataclasses import dataclass
from typing import List, Tuple

from cascadeflow.agent import CascadeAgent


@dataclass
class ProviderComparisonResult:
    """Single provider comparison test result."""

    query: str
    query_type: str  # "simple", "complex", "technical", "creative"

    # OpenAI verifier results
    openai_quality_score: float
    openai_accepted: bool
    openai_latency_ms: float
    openai_cost: float

    # Anthropic verifier results
    anthropic_quality_score: float
    anthropic_accepted: bool
    anthropic_latency_ms: float
    anthropic_cost: float

    # Comparison
    score_difference: float  # abs(openai - anthropic)
    agreement: bool  # Both accepted or both rejected
    faster_provider: str  # "openai" or "anthropic"


# Test queries organized by type
SIMPLE_QUERIES = [
    "What is 2+2?",
    "What is the capital of France?",
    "Who wrote Romeo and Juliet?",
    "What color is the sky?",
    "How many days in a week?",
]

COMPLEX_QUERIES = [
    "Explain the concept of quantum entanglement and its implications for quantum computing.",
    "What are the key differences between supervised and unsupervised machine learning?",
    "Describe the process of photosynthesis in plants at the molecular level.",
    "How does blockchain technology ensure transaction security and immutability?",
    "Explain the economic concept of supply and demand with real-world examples.",
]

TECHNICAL_QUERIES = [
    "Implement a binary search algorithm in Python with time complexity analysis.",
    "Explain the CAP theorem in distributed systems with examples.",
    "What is the difference between REST and GraphQL APIs?",
    "Describe how JWT tokens work for authentication.",
    "How does database indexing improve query performance?",
]

CREATIVE_QUERIES = [
    "Write a haiku about artificial intelligence.",
    "Describe a sunset using metaphors.",
    "Create a short story beginning with 'Once upon a time in a digital world...'",
    "Suggest three creative names for a coffee shop.",
    "Write a product description for an invisible umbrella.",
]


async def test_provider_comparison():
    """Run provider comparison benchmark."""

    print("\n" + "=" * 80)
    print("PROVIDER COMPARISON BENCHMARK: OpenAI vs Anthropic")
    print("=" * 80 + "\n")

    # Verify API keys
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        return

    print("Configuration:")
    print("  Drafter:         gpt-4o-mini (shared for both)")
    print("  OpenAI Verifier: gpt-4o")
    print("  Anthropic Verifier: claude-sonnet-4-5-20250929")
    print("  Quality Threshold: 0.7 (same for both)\n")

    results: List[ProviderComparisonResult] = []

    # Test configurations
    test_sets = [
        ("simple", SIMPLE_QUERIES),
        ("complex", COMPLEX_QUERIES),
        ("technical", TECHNICAL_QUERIES),
        ("creative", CREATIVE_QUERIES),
    ]

    for query_type, queries in test_sets:
        print(f"\n{'='*80}")
        print(f"Testing: {query_type.upper()} Queries")
        print("=" * 80 + "\n")

        for idx, query in enumerate(queries, 1):
            query_preview = query[:60] + "..." if len(query) > 60 else query
            print(f"Query {idx}/{len(queries)}: {query_preview}")

            try:
                # Test with OpenAI verifier
                print("  Testing OpenAI verifier...", end="", flush=True)
                openai_agent = CascadeAgent(
                    models=[
                        {"name": "gpt-4o-mini", "provider": "openai"},
                        {"name": "gpt-4o", "provider": "openai"},
                    ],
                    quality={"threshold": 0.7},
                )

                openai_start = time.time()
                openai_result = await openai_agent.arun(query)
                openai_latency = (time.time() - openai_start) * 1000

                openai_quality = openai_result.get("quality_score", 0.0)
                openai_accepted = openai_result.get("model_used") == "gpt-4o-mini"
                openai_cost = openai_result.get("total_cost", 0.0)

                print(
                    f" Quality: {openai_quality:.2f}, "
                    f"{'✅ Accepted' if openai_accepted else '❌ Escalated'}, "
                    f"{openai_latency:.0f}ms"
                )

                # Test with Anthropic verifier
                print("  Testing Anthropic verifier...", end="", flush=True)
                anthropic_agent = CascadeAgent(
                    models=[
                        {"name": "gpt-4o-mini", "provider": "openai"},
                        {
                            "name": "claude-sonnet-4-5-20250929",
                            "provider": "anthropic",
                        },
                    ],
                    quality={"threshold": 0.7},
                )

                anthropic_start = time.time()
                anthropic_result = await anthropic_agent.arun(query)
                anthropic_latency = (time.time() - anthropic_start) * 1000

                anthropic_quality = anthropic_result.get("quality_score", 0.0)
                anthropic_accepted = anthropic_result.get("model_used") == "gpt-4o-mini"
                anthropic_cost = anthropic_result.get("total_cost", 0.0)

                print(
                    f" Quality: {anthropic_quality:.2f}, "
                    f"{'✅ Accepted' if anthropic_accepted else '❌ Escalated'}, "
                    f"{anthropic_latency:.0f}ms"
                )

                # Compare
                score_diff = abs(openai_quality - anthropic_quality)
                agreement = openai_accepted == anthropic_accepted
                faster = "openai" if openai_latency < anthropic_latency else "anthropic"

                print(
                    f"  Comparison: Score Δ={score_diff:.2f}, "
                    f"{'✅ Agreement' if agreement else '❌ Disagree'}, "
                    f"Faster: {faster}\n"
                )

                # Record result
                result = ProviderComparisonResult(
                    query=query,
                    query_type=query_type,
                    openai_quality_score=openai_quality,
                    openai_accepted=openai_accepted,
                    openai_latency_ms=openai_latency,
                    openai_cost=openai_cost,
                    anthropic_quality_score=anthropic_quality,
                    anthropic_accepted=anthropic_accepted,
                    anthropic_latency_ms=anthropic_latency,
                    anthropic_cost=anthropic_cost,
                    score_difference=score_diff,
                    agreement=agreement,
                    faster_provider=faster,
                )
                results.append(result)

            except Exception as e:
                print(f"  ❌ Error: {e}\n")
                continue

    # Generate analysis
    print_analysis(results)


def print_analysis(results: List[ProviderComparisonResult]):
    """Print comprehensive analysis of provider comparison."""

    if not results:
        print("\n⚠️  No results to analyze")
        return

    print("\n" + "=" * 80)
    print("PROVIDER COMPARISON ANALYSIS")
    print("=" * 80 + "\n")

    # Overall statistics
    total_tests = len(results)
    agreements = sum(1 for r in results if r.agreement)
    disagreements = total_tests - agreements

    print("OVERALL STATISTICS:")
    print(f"  Total Tests:       {total_tests}")
    print(f"  Agreements:        {agreements} ({agreements/total_tests*100:.1f}%)")
    print(f"  Disagreements:     {disagreements} ({disagreements/total_tests*100:.1f}%)")

    # Quality score analysis
    avg_openai_quality = sum(r.openai_quality_score for r in results) / total_tests
    avg_anthropic_quality = sum(r.anthropic_quality_score for r in results) / total_tests
    avg_score_diff = sum(r.score_difference for r in results) / total_tests

    print("\nQUALITY SCORE ANALYSIS:")
    print(f"  OpenAI Avg Quality:      {avg_openai_quality:.3f}")
    print(f"  Anthropic Avg Quality:   {avg_anthropic_quality:.3f}")
    print(f"  Average Score Difference: {avg_score_diff:.3f}")

    # Acceptance rate
    openai_accepted = sum(1 for r in results if r.openai_accepted)
    anthropic_accepted = sum(1 for r in results if r.anthropic_accepted)

    print("\nACCEPTANCE RATES:")
    print(
        f"  OpenAI Acceptance:    {openai_accepted}/{total_tests} ({openai_accepted/total_tests*100:.1f}%)"
    )
    print(
        f"  Anthropic Acceptance: {anthropic_accepted}/{total_tests} ({anthropic_accepted/total_tests*100:.1f}%)"
    )

    # Latency comparison
    avg_openai_latency = sum(r.openai_latency_ms for r in results) / total_tests
    avg_anthropic_latency = sum(r.anthropic_latency_ms for r in results) / total_tests
    openai_faster = sum(1 for r in results if r.faster_provider == "openai")

    print("\nLATENCY COMPARISON:")
    print(f"  OpenAI Avg Latency:      {avg_openai_latency:.0f}ms")
    print(f"  Anthropic Avg Latency:   {avg_anthropic_latency:.0f}ms")
    print(
        f"  OpenAI Faster:           {openai_faster}/{total_tests} ({openai_faster/total_tests*100:.1f}%)"
    )

    # Cost comparison
    total_openai_cost = sum(r.openai_cost for r in results)
    total_anthropic_cost = sum(r.anthropic_cost for r in results)

    print("\nCOST COMPARISON:")
    print(f"  OpenAI Total Cost:       ${total_openai_cost:.6f}")
    print(f"  Anthropic Total Cost:    ${total_anthropic_cost:.6f}")
    print(f"  Cost Difference:         ${abs(total_openai_cost - total_anthropic_cost):.6f}")

    # By query type
    print("\nBY QUERY TYPE:")
    for query_type in ["simple", "complex", "technical", "creative"]:
        type_results = [r for r in results if r.query_type == query_type]
        if not type_results:
            continue

        type_agreements = sum(1 for r in type_results if r.agreement)
        type_score_diff = sum(r.score_difference for r in type_results) / len(type_results)

        print(f"\n  {query_type.title()}:")
        print(f"    Tests:           {len(type_results)}")
        print(
            f"    Agreements:      {type_agreements} ({type_agreements/len(type_results)*100:.1f}%)"
        )
        print(f"    Avg Score Δ:     {type_score_diff:.3f}")

    # Threshold recommendations
    print("\nTHRESHOLD RECOMMENDATIONS:")

    # Calculate optimal threshold for each provider
    # (threshold where acceptance rate would be ~70%)
    openai_scores = sorted([r.openai_quality_score for r in results])
    anthropic_scores = sorted([r.anthropic_quality_score for r in results])

    optimal_openai = openai_scores[int(len(openai_scores) * 0.7)]
    optimal_anthropic = anthropic_scores[int(len(anthropic_scores) * 0.7)]

    print(f"  OpenAI Optimal Threshold:    {optimal_openai:.2f} (for ~70% acceptance)")
    print(f"  Anthropic Optimal Threshold: {optimal_anthropic:.2f} (for ~70% acceptance)")

    if abs(optimal_openai - optimal_anthropic) > 0.05:
        print(
            f"\n  ⚠️  RECOMMENDATION: Use provider-specific thresholds (difference: {abs(optimal_openai - optimal_anthropic):.2f})"
        )
    else:
        print("\n  ✅ Same threshold works for both providers")

    # Key findings
    print("\nKEY FINDINGS:")
    if avg_score_diff > 0.15:
        print("  ⚠️  High score variance between providers - consider calibration")
    if disagreements / total_tests > 0.3:
        print("  ⚠️  High disagreement rate - providers evaluate quality differently")
    if abs(avg_openai_latency - avg_anthropic_latency) > 200:
        faster = "OpenAI" if avg_openai_latency < avg_anthropic_latency else "Anthropic"
        print(f"  ⚡ {faster} is significantly faster for quality scoring")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_provider_comparison())
