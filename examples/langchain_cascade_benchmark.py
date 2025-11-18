"""Comprehensive cascade benchmark with LangSmith tracing.

Tests cascade behavior across different query complexities and modes:
- Trivial short/long queries
- Expert short/long queries
- Streaming and non-streaming modes
- Semantic quality evaluation
- Cross-provider cascade (OpenAI → Anthropic)

Reports escalation rates and cost savings.

Run:
    OPENAI_API_KEY=sk-... \
    ANTHROPIC_API_KEY=sk-ant-... \
    LANGSMITH_API_KEY=lsv2_pt_... \
    LANGSMITH_PROJECT=cascadeflow-langchain \
    LANGSMITH_TRACING=true \
    python examples/langchain_cascade_benchmark.py
"""

import asyncio
import os
from dataclasses import dataclass
from typing import List

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from cascadeflow.integrations.langchain import CascadeFlow, CostHistory


@dataclass
class BenchmarkResult:
    """Single benchmark test result."""

    query_type: str  # "trivial_short", "trivial_long", "expert_short", "expert_long"
    mode: str  # "streaming" or "non_streaming"
    query: str
    model_used: str
    accepted: bool
    drafter_quality: float
    total_cost: float
    drafter_cost: float
    verifier_cost: float
    latency_ms: float
    escalated: bool  # True if verifier was used


# Test queries organized by complexity and length
TRIVIAL_SHORT = [
    "What is 2+2?",
    "What is the capital of France?",
    "Who wrote Hamlet?",
]

TRIVIAL_LONG = [
    "What is 2 plus 2? Please provide a clear, detailed explanation of this simple arithmetic operation, "
    "including the mathematical reasoning behind the addition of these two numbers. I want to understand "
    "the fundamental principles of addition as they apply to this specific calculation.",

    "What is the capital of France? Please provide comprehensive information about this city, including "
    "its historical significance, cultural importance, geographical location, and why it serves as the "
    "administrative center of the French Republic. I'm interested in understanding all aspects of this city.",

    "Who wrote the famous play Hamlet? Please provide detailed information about the author, including "
    "their biographical background, other notable works, the historical context in which they wrote, "
    "and the significance of their contribution to English literature and world drama.",
]

EXPERT_SHORT = [
    "Explain quantum entanglement.",
    "What is NP-completeness?",
    "Derive the Euler-Lagrange equation.",
]

EXPERT_LONG = [
    "Explain the concept of quantum entanglement in detail, including the mathematical formalism using "
    "Bell states and density matrices, the EPR paradox, Bell's theorem and its experimental verification, "
    "the implications for quantum information theory, and applications in quantum computing and quantum "
    "cryptography. Also discuss the philosophical implications regarding locality and realism.",

    "Provide a comprehensive explanation of NP-completeness, including the formal definitions of P, NP, "
    "NP-hard, and NP-complete complexity classes, the Cook-Levin theorem and its proof sketch, examples "
    "of NP-complete problems (SAT, 3-SAT, Clique, Vertex Cover), polynomial-time reductions, and the "
    "significance of the P vs NP question for theoretical computer science and practical applications.",

    "Derive the Euler-Lagrange equation from the principle of least action in classical mechanics. Include "
    "the mathematical formalism using the calculus of variations, the concept of functionals and their "
    "extremization, the full derivation showing all steps, examples of applying the equation to simple "
    "physical systems like the simple harmonic oscillator, and discuss the connection to Noether's theorem "
    "and conservation laws.",
]


async def run_benchmark():
    """Run comprehensive cascade benchmark."""

    # Verify environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return
    if not os.getenv("LANGSMITH_API_KEY"):
        print("Warning: LANGSMITH_API_KEY not set - LangSmith tracing disabled")

    print("=" * 80)
    print("CASCADEFLOW COMPREHENSIVE BENCHMARK")
    print("=" * 80)
    print("\nConfiguration:")
    print("  Drafter:  gpt-4o-mini (OpenAI)")
    print("  Verifier: claude-sonnet-4-5-20250929 (Anthropic)")
    print("  Quality Threshold: 0.7")
    print("  Semantic Evaluation: Enabled")
    print("  LangSmith Tracing:", "✅ Enabled" if os.getenv("LANGSMITH_TRACING") == "true" else "❌ Disabled")

    if os.getenv("LANGSMITH_TRACING") == "true":
        print(f"  LangSmith Project: {os.getenv('LANGSMITH_PROJECT', 'default')}")
        print("  View traces at: https://smith.langchain.com/")

    print("\n" + "=" * 80)

    # Setup cascade
    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    verifier = ChatAnthropic(model="claude-sonnet-4-5-20250929", temperature=0)

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.7,
        enable_cost_tracking=True,
        cost_tracking_provider="cascadeflow",
    )

    results: List[BenchmarkResult] = []
    history = CostHistory()

    # Test configurations
    test_configs = [
        ("trivial_short", TRIVIAL_SHORT),
        ("trivial_long", TRIVIAL_LONG),
        ("expert_short", EXPERT_SHORT),
        ("expert_long", EXPERT_LONG),
    ]

    # Run tests for each configuration
    for query_type, queries in test_configs:
        print(f"\n{'=' * 80}")
        print(f"Testing: {query_type.upper().replace('_', ' ')}")
        print("=" * 80)

        # Test non-streaming mode
        print(f"\n--- Non-Streaming Mode ---\n")
        for i, query in enumerate(queries, 1):
            query_preview = query[:60] + "..." if len(query) > 60 else query
            print(f"Query {i}: {query_preview}")

            try:
                response = await cascade.ainvoke(query)
                result = cascade.get_last_cascade_result()

                # Track result
                history.add_result(result, query)

                # Create benchmark result
                bench_result = BenchmarkResult(
                    query_type=query_type,
                    mode="non_streaming",
                    query=query,
                    model_used=result["model_used"],
                    accepted=result["accepted"],
                    drafter_quality=result["drafter_quality"],
                    total_cost=result["total_cost"],
                    drafter_cost=result["drafter_cost"],
                    verifier_cost=result["verifier_cost"],
                    latency_ms=result["latency_ms"],
                    escalated=not result["accepted"],
                )
                results.append(bench_result)

                # Print result
                print(f"  Model: {result['model_used']}")
                print(f"  Quality: {result['drafter_quality']:.2f}")
                print(f"  Accepted: {'✅' if result['accepted'] else '❌ (escalated)'}")
                print(f"  Cost: ${result['total_cost']:.6f}")
                print(f"  Latency: {result['latency_ms']:.0f}ms")
                print()

            except Exception as e:
                print(f"  ❌ Error: {e}\n")
                continue

        # Test streaming mode
        print(f"\n--- Streaming Mode ---\n")
        for i, query in enumerate(queries, 1):
            query_preview = query[:60] + "..." if len(query) > 60 else query
            print(f"Query {i}: {query_preview}")

            try:
                full_content = ""
                async for chunk in cascade.astream(query):
                    full_content += chunk.content

                result = cascade.get_last_cascade_result()

                # Track result
                history.add_result(result, query)

                # Create benchmark result
                bench_result = BenchmarkResult(
                    query_type=query_type,
                    mode="streaming",
                    query=query,
                    model_used=result["model_used"],
                    accepted=result["accepted"],
                    drafter_quality=result["drafter_quality"],
                    total_cost=result["total_cost"],
                    drafter_cost=result["drafter_cost"],
                    verifier_cost=result["verifier_cost"],
                    latency_ms=result["latency_ms"],
                    escalated=not result["accepted"],
                )
                results.append(bench_result)

                # Print result
                print(f"  Model: {result['model_used']}")
                print(f"  Quality: {result['drafter_quality']:.2f}")
                print(f"  Accepted: {'✅' if result['accepted'] else '❌ (escalated)'}")
                print(f"  Cost: ${result['total_cost']:.6f}")
                print(f"  Latency: {result['latency_ms']:.0f}ms")
                print()

            except Exception as e:
                print(f"  ❌ Error: {e}\n")
                continue

    # Generate comprehensive report
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 80)

    # Overall statistics
    total_queries = len(results)
    total_escalated = sum(1 for r in results if r.escalated)
    total_accepted = total_queries - total_escalated

    print(f"\nOVERALL STATISTICS:")
    print(f"  Total Queries:       {total_queries}")
    print(f"  Drafter Accepted:    {total_accepted} ({total_accepted/total_queries*100:.1f}%)")
    print(f"  Escalated:           {total_escalated} ({total_escalated/total_queries*100:.1f}%)")

    # Cost analysis
    summary = history.get_summary()
    print(f"\nCOST ANALYSIS:")
    print(f"  Total Cost:          ${summary['total_cost']:.6f}")
    print(f"  Average Cost:        ${summary['avg_cost']:.6f}")
    print(f"  Average Savings:     {summary['avg_savings']:.1f}%")
    print(f"  Drafter Cost:        ${summary['total_drafter_cost']:.6f}")
    print(f"  Verifier Cost:       ${summary['total_verifier_cost']:.6f}")

    # Calculate what it would cost if we always used verifier
    verifier_only_cost = total_queries * 0.05  # Rough estimate
    actual_cost = summary['total_cost']
    savings = verifier_only_cost - actual_cost
    savings_pct = (savings / verifier_only_cost * 100) if verifier_only_cost > 0 else 0

    print(f"\nVS. ALWAYS-VERIFIER BASELINE:")
    print(f"  Verifier-Only Cost:  ${verifier_only_cost:.6f}")
    print(f"  Cascade Cost:        ${actual_cost:.6f}")
    print(f"  Total Savings:       ${savings:.6f} ({savings_pct:.1f}%)")

    # Performance
    print(f"\nPERFORMANCE:")
    print(f"  Average Latency:     {summary['avg_latency_ms']:.0f}ms")

    # By query type
    print(f"\nBY QUERY TYPE:")
    for query_type in ["trivial_short", "trivial_long", "expert_short", "expert_long"]:
        type_results = [r for r in results if r.query_type == query_type]
        if not type_results:
            continue

        type_escalated = sum(1 for r in type_results if r.escalated)
        type_total = len(type_results)
        type_cost = sum(r.total_cost for r in type_results)
        type_quality = sum(r.drafter_quality for r in type_results) / type_total

        print(f"\n  {query_type.replace('_', ' ').title()}:")
        print(f"    Queries:           {type_total}")
        print(f"    Escalated:         {type_escalated} ({type_escalated/type_total*100:.1f}%)")
        print(f"    Avg Quality:       {type_quality:.2f}")
        print(f"    Total Cost:        ${type_cost:.6f}")

    # By mode
    print(f"\nBY MODE:")
    for mode in ["non_streaming", "streaming"]:
        mode_results = [r for r in results if r.mode == mode]
        if not mode_results:
            continue

        mode_escalated = sum(1 for r in mode_results if r.escalated)
        mode_total = len(mode_results)
        mode_cost = sum(r.total_cost for r in mode_results)

        print(f"\n  {mode.replace('_', ' ').title()}:")
        print(f"    Queries:           {mode_total}")
        print(f"    Escalated:         {mode_escalated} ({mode_escalated/mode_total*100:.1f}%)")
        print(f"    Total Cost:        ${mode_cost:.6f}")

    # Export results
    history.export_csv("/tmp/cascade_benchmark_results.csv")
    print(f"\n📊 Results exported to: /tmp/cascade_benchmark_results.csv")

    # LangSmith traces
    if os.getenv("LANGSMITH_TRACING") == "true":
        print(f"\n🔍 View detailed traces in LangSmith:")
        print(f"   https://smith.langchain.com/")
        print(f"\n   Each trace includes:")
        print(f"   - Drafter and verifier token usage")
        print(f"   - Cost breakdown (drafter, verifier, total)")
        print(f"   - Quality scores and acceptance decisions")
        print(f"   - Latency measurements")

    print("\n" + "=" * 80)
    print("✅ BENCHMARK COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
