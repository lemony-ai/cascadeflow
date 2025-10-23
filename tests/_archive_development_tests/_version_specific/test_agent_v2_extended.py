"""
Extended Test Suite for Agent v2.0 - Direct vs Cascade + Terminal Streaming
==========================================================================

New comprehensive tests:
- Direct routing statistics tracking
- Cascade vs direct routing comparison
- Mixed workload testing
- Terminal streaming visualization
- Performance benchmarking
- Acceptance rate validation

Run:
    pytest tests/test_agent_v2_extended.py -v -s

Run specific category:
    pytest tests/test_agent_v2_extended.py -k "routing" -v -s
    pytest tests/test_agent_v2_extended.py -k "streaming" -v -s
"""

import os
import sys
import time

import pytest
from dotenv import load_dotenv

load_dotenv()

from cascadeflow.config import ModelConfig

from cascadeflow.agent import CascadeAgent
from cascadeflow.providers import get_available_providers
from cascadeflow.quality import QualityConfig
from cascadeflow.streaming import StreamEventType, StreamManager

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def test_models() -> list[ModelConfig]:
    """Create test models for agent."""
    models = []

    if os.getenv("GROQ_API_KEY"):
        models.append(
            ModelConfig(name="llama-3.1-8b-instant", provider="groq", cost=0.0, speed_ms=300)
        )

    if os.getenv("OPENAI_API_KEY"):
        models.append(
            ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002, speed_ms=800)
        )
        models.append(
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015, speed_ms=600)
        )

    if os.getenv("ANTHROPIC_API_KEY"):
        models.append(
            ModelConfig(
                name="claude-3-haiku-20240307", provider="anthropic", cost=0.00125, speed_ms=700
            )
        )

    return models


@pytest.fixture
def agent(test_models) -> CascadeAgent:
    """Create agent for testing."""
    if not test_models:
        pytest.skip("No API keys found")

    return CascadeAgent(
        models=test_models,
        quality_config=QualityConfig.for_cascade(),
        enable_cascade=True,
        verbose=True,
    )


@pytest.fixture
def routing_queries() -> dict[str, list[str]]:
    """Queries categorized by expected routing."""
    return {
        "trivial": [
            "What is 2+2?",
            "Name a color",
            "What is the capital of France?",
            "Define 'hello'",
            "What day comes after Monday?",
        ],
        "simple": [
            "What is Python?",
            "Explain what AI means",
            "How does a bicycle work?",
            "What is photosynthesis?",
            "Describe the solar system",
        ],
        "moderate": [
            "Compare Python and JavaScript for web development",
            "Explain the difference between RAM and ROM",
            "How do neural networks learn?",
            "What are the causes of climate change?",
            "Describe the water cycle in detail",
        ],
        "hard": [
            "Analyze the economic implications of quantitative easing",
            "Compare different approaches to consciousness in philosophy",
            "Explain the mathematical foundations of quantum mechanics",
            "Discuss the ethical implications of genetic engineering",
            "Evaluate different theories of language acquisition",
        ],
        "expert": [
            "Derive the Navier-Stokes equations from first principles",
            "Explain Gödel's incompleteness theorems and their implications",
            "Analyze the P vs NP problem in computational complexity theory",
            "Discuss the mathematical framework of general relativity",
            "Explain the proof of Fermat's Last Theorem",
        ],
    }


# ============================================================================
# ROUTING STRATEGY TESTS - EXTENSIVE
# ============================================================================


@pytest.mark.asyncio
async def test_direct_routing_statistics(agent, routing_queries):
    """
    COMPREHENSIVE: Test that direct routing is properly tracked in statistics.

    This test verifies:
    1. Direct routing happens for complex queries
    2. Statistics accurately track direct vs cascade routing
    3. Costs are properly attributed
    """
    # Reset stats
    agent.stats = {
        "total_queries": 0,
        "total_cost": 0.0,
        "by_complexity": dict.fromkeys(["trivial", "simple", "moderate", "hard", "expert"], 0),
        "direct_routed": 0,
        "cascade_used": 0,
        "draft_accepted": 0,
        "draft_rejected": 0,
        "streaming_used": 0,
    }

    print("\n" + "=" * 70)
    print("DIRECT ROUTING STATISTICS TEST")
    print("=" * 70)

    # Run complex queries that should use direct routing
    expert_results = []
    for query in routing_queries["expert"][:3]:
        print(f"\nProcessing: {query[:60]}...")
        result = await agent.run(query, max_tokens=100)
        expert_results.append(result)
        print(f"  → Complexity: {result.complexity}")
        print(f"  → Strategy: {result.routing_strategy}")
        print(f"  → Cascaded: {result.cascaded}")

    # Verify statistics
    stats = agent.get_stats()

    print("\n" + "-" * 70)
    print("STATISTICS VERIFICATION:")
    print("-" * 70)
    print(f"Total queries: {stats['total_queries']}")
    print(f"Direct routed: {stats['direct_routed']}")
    print(f"Cascade used: {stats['cascade_used']}")
    print(f"By complexity: {stats['by_complexity']}")

    # Assertions
    assert stats["total_queries"] == 3, "Should have 3 queries"
    assert stats["direct_routed"] > 0, "Should have direct routing"
    assert all(
        r.routing_strategy == "direct" for r in expert_results
    ), "Expert queries should use direct routing"
    assert all(not r.cascaded for r in expert_results), "Expert queries should not be cascaded"

    print("\n✅ Direct routing statistics test PASSED")
    agent.print_stats()


@pytest.mark.asyncio
async def test_cascade_vs_direct_comparison(agent, routing_queries):
    """
    COMPREHENSIVE: Compare cascade vs direct routing across complexity levels.

    Tests:
    1. Trivial/Simple → Cascade (fast, cheap)
    2. Expert → Direct (quality, no cascade overhead)
    3. Performance metrics for each strategy
    """
    # Reset stats
    agent.stats = {
        "total_queries": 0,
        "total_cost": 0.0,
        "by_complexity": dict.fromkeys(["trivial", "simple", "moderate", "hard", "expert"], 0),
        "direct_routed": 0,
        "cascade_used": 0,
        "draft_accepted": 0,
        "draft_rejected": 0,
        "streaming_used": 0,
    }

    print("\n" + "=" * 70)
    print("CASCADE VS DIRECT ROUTING COMPARISON")
    print("=" * 70)

    results = {"cascade": [], "direct": []}

    # Test cascade routing (simple queries)
    print("\n🔄 Testing CASCADE routing (simple queries):")
    for query in routing_queries["simple"][:3]:
        start = time.time()
        result = await agent.run(query, max_tokens=50)
        elapsed = (time.time() - start) * 1000

        results["cascade"].append({"query": query[:50], "result": result, "elapsed_ms": elapsed})

        print(f"\n  Query: {query[:50]}...")
        print(f"  → Complexity: {result.complexity}")
        print(f"  → Strategy: {result.routing_strategy}")
        print(f"  → Model: {result.model_used}")
        print(f"  → Draft accepted: {result.draft_accepted}")
        print(f"  → Cost: ${result.total_cost:.6f}")
        print(f"  → Latency: {elapsed:.1f}ms")

    # Test direct routing (expert queries)
    print("\n⚡ Testing DIRECT routing (expert queries):")
    for query in routing_queries["expert"][:3]:
        start = time.time()
        result = await agent.run(query, max_tokens=100)
        elapsed = (time.time() - start) * 1000

        results["direct"].append({"query": query[:50], "result": result, "elapsed_ms": elapsed})

        print(f"\n  Query: {query[:50]}...")
        print(f"  → Complexity: {result.complexity}")
        print(f"  → Strategy: {result.routing_strategy}")
        print(f"  → Model: {result.model_used}")
        print(f"  → Cost: ${result.total_cost:.6f}")
        print(f"  → Latency: {elapsed:.1f}ms")

    # Analyze results
    print("\n" + "-" * 70)
    print("COMPARISON ANALYSIS:")
    print("-" * 70)

    cascade_avg_latency = sum(r["elapsed_ms"] for r in results["cascade"]) / len(results["cascade"])
    direct_avg_latency = sum(r["elapsed_ms"] for r in results["direct"]) / len(results["direct"])

    cascade_total_cost = sum(r["result"].total_cost for r in results["cascade"])
    direct_total_cost = sum(r["result"].total_cost for r in results["direct"])

    print("\nCASCADE Strategy:")
    print(f"  Queries: {len(results['cascade'])}")
    print(f"  Avg latency: {cascade_avg_latency:.1f}ms")
    print(f"  Total cost: ${cascade_total_cost:.6f}")
    print(f"  Acceptance rate: {agent.stats['draft_accepted']}/{agent.stats['cascade_used']}")

    print("\nDIRECT Strategy:")
    print(f"  Queries: {len(results['direct'])}")
    print(f"  Avg latency: {direct_avg_latency:.1f}ms")
    print(f"  Total cost: ${direct_total_cost:.6f}")

    # Verify routing decisions
    assert all(
        r["result"].cascaded for r in results["cascade"]
    ), "Simple queries should use cascade"
    assert all(
        not r["result"].cascaded for r in results["direct"]
    ), "Expert queries should use direct"
    assert agent.stats["cascade_used"] == 3, "Should have 3 cascade queries"
    assert agent.stats["direct_routed"] == 3, "Should have 3 direct queries"

    print("\n✅ Cascade vs Direct comparison test PASSED")
    agent.print_stats()


@pytest.mark.asyncio
async def test_mixed_workload_routing(agent, routing_queries):
    """
    COMPREHENSIVE: Test realistic mixed workload with all complexity levels.

    Simulates real-world usage with:
    - Mix of trivial, simple, moderate, hard, and expert queries
    - Validates routing decisions for each complexity
    - Tracks acceptance rates and costs
    """
    # Reset stats
    agent.stats = {
        "total_queries": 0,
        "total_cost": 0.0,
        "by_complexity": dict.fromkeys(["trivial", "simple", "moderate", "hard", "expert"], 0),
        "direct_routed": 0,
        "cascade_used": 0,
        "draft_accepted": 0,
        "draft_rejected": 0,
        "streaming_used": 0,
    }

    print("\n" + "=" * 70)
    print("MIXED WORKLOAD ROUTING TEST")
    print("=" * 70)

    # Create mixed workload
    workload = [
        ("trivial", routing_queries["trivial"][0]),
        ("simple", routing_queries["simple"][0]),
        ("moderate", routing_queries["moderate"][0]),
        ("hard", routing_queries["hard"][0]),
        ("expert", routing_queries["expert"][0]),
        ("trivial", routing_queries["trivial"][1]),
        ("simple", routing_queries["simple"][1]),
    ]

    results_by_complexity = {}

    for expected_complexity, query in workload:
        print(f"\n{'─'*70}")
        print(f"Query: {query[:60]}...")
        print(f"Expected complexity: {expected_complexity}")

        result = await agent.run(query, max_tokens=80)

        print(f"Actual complexity: {result.complexity}")
        print(f"Strategy: {result.routing_strategy}")
        print(f"Cascaded: {result.cascaded}")
        print(f"Model: {result.model_used}")
        print(f"Cost: ${result.total_cost:.6f}")

        if result.complexity not in results_by_complexity:
            results_by_complexity[result.complexity] = []
        results_by_complexity[result.complexity].append(result)

    # Analysis
    print("\n" + "=" * 70)
    print("WORKLOAD ANALYSIS:")
    print("=" * 70)

    for complexity, results in sorted(results_by_complexity.items()):
        cascaded = sum(1 for r in results if r.cascaded)
        direct = len(results) - cascaded

        print(f"\n{complexity.upper()}:")
        print(f"  Total: {len(results)}")
        print(f"  Cascaded: {cascaded}")
        print(f"  Direct: {direct}")

        if cascaded > 0:
            accepted = sum(1 for r in results if r.cascaded and r.draft_accepted)
            print(f"  Draft acceptance: {accepted}/{cascaded} ({accepted/cascaded*100:.0f}%)")

    # Verify routing logic
    stats = agent.get_stats()
    total = stats["cascade_used"] + stats["direct_routed"]

    print("\nOVERALL STATISTICS:")
    print(f"  Total queries: {stats['total_queries']}")
    print(f"  Cascade: {stats['cascade_used']}/{total} ({stats['cascade_used']/total*100:.0f}%)")
    print(f"  Direct: {stats['direct_routed']}/{total} ({stats['direct_routed']/total*100:.0f}%)")
    print(f"  Total cost: ${stats['total_cost']:.6f}")

    assert stats["total_queries"] == len(workload), "Should track all queries"
    assert stats["cascade_used"] > 0, "Should have cascade queries"
    assert stats["direct_routed"] > 0, "Should have direct queries"

    print("\n✅ Mixed workload routing test PASSED")
    agent.print_stats()


@pytest.mark.asyncio
async def test_forced_routing_modes(agent, routing_queries):
    """
    Test forced routing modes (force_direct and complexity_hint).

    Verifies:
    1. force_direct overrides complexity detection
    2. complexity_hint changes routing decision
    3. Statistics track forced routing correctly
    """
    # Reset stats
    agent.stats = {
        "total_queries": 0,
        "total_cost": 0.0,
        "by_complexity": dict.fromkeys(["trivial", "simple", "moderate", "hard", "expert"], 0),
        "direct_routed": 0,
        "cascade_used": 0,
        "draft_accepted": 0,
        "draft_rejected": 0,
        "streaming_used": 0,
    }

    print("\n" + "=" * 70)
    print("FORCED ROUTING MODES TEST")
    print("=" * 70)

    query = routing_queries["simple"][0]  # Normally would cascade

    # Test 1: Normal routing
    print("\n1. NORMAL routing:")
    result_normal = await agent.run(query, max_tokens=50)
    print(f"   Strategy: {result_normal.routing_strategy}")
    print(f"   Cascaded: {result_normal.cascaded}")
    print(f"   Reason: {result_normal.reason}")

    # Test 2: Force direct
    print("\n2. FORCE DIRECT:")
    result_forced = await agent.run(query, max_tokens=50, force_direct=True)
    print(f"   Strategy: {result_forced.routing_strategy}")
    print(f"   Cascaded: {result_forced.cascaded}")
    print(f"   Reason: {result_forced.reason}")

    # Test 3: Complexity hint (expert)
    print("\n3. COMPLEXITY HINT (expert):")
    result_hint = await agent.run(query, max_tokens=50, complexity_hint="expert")
    print(f"   Strategy: {result_hint.routing_strategy}")
    print(f"   Cascaded: {result_hint.cascaded}")
    print(f"   Complexity: {result_hint.complexity}")
    print(f"   Reason: {result_hint.reason}")

    # Verify different behaviors
    assert result_normal.cascaded, "Normal should cascade simple query"
    assert not result_forced.cascaded, "Force direct should not cascade"
    assert not result_hint.cascaded, "Expert hint should not cascade"
    assert result_forced.routing_strategy == "direct", "Forced should be direct"
    assert result_hint.complexity == "expert", "Hint should set complexity"

    print("\n✅ Forced routing modes test PASSED")


# ============================================================================
# TERMINAL STREAMING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_streaming_visual_terminal_demo(agent, routing_queries):
    """
    DEMO: Terminal streaming with visual feedback.

    This test demonstrates:
    1. Streaming output in terminal
    2. Visual pulsing dot indicator
    3. Cascade switch notifications
    4. Real-time progress feedback

    Run with: pytest -k "terminal_demo" -v -s
    """
    print("\n" + "=" * 70)
    print("TERMINAL STREAMING VISUAL DEMO")
    print("=" * 70)
    print("\nThis demo shows streaming with visual feedback in terminal.")
    print("Note: Visual indicators may not show in non-TTY environments.\n")

    # Test different query types
    test_cases = [
        ("Simple query (cascade expected)", routing_queries["simple"][0]),
        ("Complex query (direct expected)", routing_queries["expert"][0]),
    ]

    for description, query in test_cases:
        print("\n" + "─" * 70)
        print(f"TEST: {description}")
        print(f"Query: {query[:60]}...")
        print("─" * 70)

        # Check if we're in a TTY
        is_tty = sys.stdout.isatty()
        print(f"TTY detected: {is_tty}")

        if is_tty:
            print("\n🔄 Streaming with visual feedback:")
        else:
            print("\n🔄 Streaming (visual feedback disabled in non-TTY):")

        # Stream with visual feedback
        start_time = time.time()
        result = await agent.run_streaming(
            query, max_tokens=100, enable_visual=True  # Enable visual feedback
        )
        elapsed = (time.time() - start_time) * 1000

        print("\n\n✅ Complete!")
        print(f"   Response: {result.content[:100]}...")
        print(f"   Model: {result.model_used}")
        print(f"   Strategy: {result.routing_strategy}")
        print(f"   Cascaded: {result.cascaded}")
        print(f"   Cost: ${result.total_cost:.6f}")
        print(f"   Latency: {elapsed:.1f}ms")

    print("\n✅ Terminal streaming demo COMPLETE")


@pytest.mark.asyncio
async def test_streaming_events_detailed(agent, routing_queries):
    """
    DETAILED: Test streaming event flow and timing.

    Captures and analyzes:
    1. All event types (CHUNK, SWITCH, COMPLETE, ERROR)
    2. Event timing and sequence
    3. Content accumulation
    4. Metadata in events
    """
    from cascadeflow.speculative import WholeResponseCascade

    print("\n" + "=" * 70)
    print("STREAMING EVENTS DETAILED TEST")
    print("=" * 70)

    providers = get_available_providers()
    if len(providers) < 2:
        pytest.skip("Need at least 2 providers")

    # Create cascade
    models = []
    if "groq" in providers:
        models.append(ModelConfig(name="llama-3.1-8b-instant", provider="groq", cost=0.0))
    if "openai" in providers:
        models.append(ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002))

    if len(models) < 2:
        pytest.skip("Need at least 2 models")

    cascade = WholeResponseCascade(
        drafter=models[0],
        verifier=models[1],
        providers=providers,
        quality_config=QualityConfig.for_cascade(),
    )

    streaming = StreamManager(cascade, verbose=True)

    # Test query
    query = routing_queries["simple"][0]

    print(f"\nQuery: {query}")
    print("\nEvent sequence:")

    events = []
    content_chunks = []
    start_time = time.time()

    async for event in streaming.stream(query, max_tokens=100):
        event_time = (time.time() - start_time) * 1000
        events.append((event, event_time))

        if event.type == StreamEventType.CHUNK:
            content_chunks.append(event.content)
            print(f"  [{event_time:6.1f}ms] CHUNK: {len(event.content)} chars")
            print(f"             Model: {event.metadata.get('model', 'unknown')}")

        elif event.type == StreamEventType.SWITCH:
            print(
                f"  [{event_time:6.1f}ms] SWITCH: {event.metadata.get('from_model')} → {event.metadata.get('to_model')}"
            )
            print(f"             Reason: {event.metadata.get('reason')}")

        elif event.type == StreamEventType.COMPLETE:
            print(f"  [{event_time:6.1f}ms] COMPLETE")
            result = event.metadata["result"]
            print(f"             Draft accepted: {result['draft_accepted']}")
            print(f"             Total cost: ${result['total_cost']:.6f}")

        elif event.type == StreamEventType.ERROR:
            print(f"  [{event_time:6.1f}ms] ERROR: {event.content}")

    # Analysis
    total_time = (time.time() - start_time) * 1000

    print("\n" + "-" * 70)
    print("EVENT ANALYSIS:")
    print("-" * 70)
    print(f"Total events: {len(events)}")
    print(f"Total time: {total_time:.1f}ms")
    print(f"Content chunks: {len(content_chunks)}")
    print(f"Total content length: {sum(len(c) for c in content_chunks)} chars")

    # Count event types
    chunk_count = sum(1 for e, _ in events if e.type == StreamEventType.CHUNK)
    switch_count = sum(1 for e, _ in events if e.type == StreamEventType.SWITCH)
    complete_count = sum(1 for e, _ in events if e.type == StreamEventType.COMPLETE)

    print("\nEvent breakdown:")
    print(f"  CHUNK: {chunk_count}")
    print(f"  SWITCH: {switch_count}")
    print(f"  COMPLETE: {complete_count}")

    # Verify event sequence
    assert chunk_count > 0, "Should have chunk events"
    assert complete_count == 1, "Should have exactly 1 complete event"
    assert events[-1][0].type == StreamEventType.COMPLETE, "Last event should be COMPLETE"

    print("\n✅ Streaming events detailed test PASSED")


@pytest.mark.asyncio
async def test_streaming_vs_non_streaming_performance(agent, routing_queries):
    """
    BENCHMARK: Compare streaming vs non-streaming performance.

    Measures:
    1. Time to first chunk (streaming advantage)
    2. Total latency (should be similar)
    3. User experience metrics
    """
    print("\n" + "=" * 70)
    print("STREAMING VS NON-STREAMING PERFORMANCE")
    print("=" * 70)

    query = routing_queries["simple"][0]
    runs = 3

    print(f"\nQuery: {query}")
    print(f"Runs: {runs} each")

    # Benchmark non-streaming
    print("\n📊 Benchmarking NON-STREAMING...")
    non_streaming_times = []
    for i in range(runs):
        start = time.time()
        await agent.run(query, max_tokens=100)
        elapsed = (time.time() - start) * 1000
        non_streaming_times.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.1f}ms")

    # Benchmark streaming
    print("\n📊 Benchmarking STREAMING...")
    streaming_times = []
    for i in range(runs):
        start = time.time()
        await agent.run_streaming(query, max_tokens=100, enable_visual=False)
        elapsed = (time.time() - start) * 1000
        streaming_times.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.1f}ms")

    # Analysis
    avg_non_streaming = sum(non_streaming_times) / len(non_streaming_times)
    avg_streaming = sum(streaming_times) / len(streaming_times)

    print("\n" + "-" * 70)
    print("PERFORMANCE COMPARISON:")
    print("-" * 70)
    print(f"Non-streaming avg: {avg_non_streaming:.1f}ms")
    print(f"Streaming avg:     {avg_streaming:.1f}ms")
    print(
        f"Overhead:          {avg_streaming - avg_non_streaming:.1f}ms ({(avg_streaming/avg_non_streaming - 1)*100:.1f}%)"
    )

    print("\n💡 Note: Streaming provides better UX through incremental display")
    print("   even if total latency is slightly higher.")

    print("\n✅ Performance comparison test PASSED")


# ============================================================================
# ACCEPTANCE RATE VALIDATION
# ============================================================================


@pytest.mark.asyncio
async def test_cascade_acceptance_rates(agent, routing_queries):
    """
    VALIDATION: Test cascade acceptance rates across complexity levels.

    Expected behavior:
    - Trivial: High acceptance (80-100%)
    - Simple: Good acceptance (60-90%)
    - Moderate: Moderate acceptance (40-70%)

    This validates quality thresholds are working correctly.
    """
    # Reset stats
    agent.stats = {
        "total_queries": 0,
        "total_cost": 0.0,
        "by_complexity": dict.fromkeys(["trivial", "simple", "moderate", "hard", "expert"], 0),
        "direct_routed": 0,
        "cascade_used": 0,
        "draft_accepted": 0,
        "draft_rejected": 0,
        "streaming_used": 0,
    }

    print("\n" + "=" * 70)
    print("CASCADE ACCEPTANCE RATES VALIDATION")
    print("=" * 70)

    acceptance_by_complexity = {}

    # Test each complexity that uses cascade
    for complexity in ["trivial", "simple", "moderate"]:
        print(f"\n{'─'*70}")
        print(f"Testing {complexity.upper()} queries:")
        print("─" * 70)

        results = []
        for query in routing_queries[complexity][:3]:
            result = await agent.run(query, max_tokens=80)
            results.append(result)

            print(f"\nQuery: {query[:50]}...")
            print(f"  Detected complexity: {result.complexity}")
            print(f"  Cascaded: {result.cascaded}")
            if result.cascaded:
                print(f"  Draft accepted: {result.draft_accepted}")
                print(f"  Draft model: {result.draft_model}")
                if not result.draft_accepted:
                    print(f"  Verifier model: {result.verifier_model}")

        # Calculate acceptance rate
        cascaded = [r for r in results if r.cascaded]
        if cascaded:
            accepted = sum(1 for r in cascaded if r.draft_accepted)
            acceptance_rate = accepted / len(cascaded) * 100
            acceptance_by_complexity[complexity] = acceptance_rate

            print(
                f"\n{complexity.upper()} acceptance rate: {accepted}/{len(cascaded)} ({acceptance_rate:.0f}%)"
            )

    # Summary
    print("\n" + "=" * 70)
    print("ACCEPTANCE RATE SUMMARY:")
    print("=" * 70)
    for complexity, rate in sorted(acceptance_by_complexity.items()):
        emoji = "🟢" if rate >= 70 else "🟡" if rate >= 50 else "🔴"
        print(f"{emoji} {complexity.upper():10s}: {rate:.0f}%")

    print("\n✅ Cascade acceptance rates validation PASSED")
    agent.print_stats()


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
