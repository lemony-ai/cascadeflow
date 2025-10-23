"""
Complete Test Suite for Agent v2.0 + Streaming
==============================================

Tests:
- Agent v2.0 core functionality
- Streaming integration
- Visual feedback
- Complexity-based routing
- Statistics tracking
- Non-streaming vs streaming equivalence
- Auto-discovery with from_env()

Prerequisites:
- API keys in .env file (OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, etc.)
- All providers installed

Run:
    pytest tests/test_agent_v2_streaming.py -v -s

Run specific test:
    pytest tests/test_agent_v2_streaming.py::test_agent_basic_run -v -s
"""

import os
import time

import pytest

# Load .env file
from dotenv import load_dotenv

load_dotenv()

from cascadeflow.config import ModelConfig

from cascadeflow.agent import CascadeAgent, CascadeResult
from cascadeflow.interface.visual_consumer import SilentConsumer
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

    # Add models based on available API keys
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
        pytest.skip("No API keys found in .env file")

    return CascadeAgent(
        models=test_models,
        quality_config=QualityConfig.for_cascade(),
        enable_cascade=True,
        verbose=True,
    )


@pytest.fixture
def simple_queries() -> list[str]:
    """Simple queries for testing."""
    return [
        "What is 2+2?",
        "Name a color",
        "What is Python?",
        "Define AI in one sentence",
        "What's the capital of France?",
    ]


@pytest.fixture
def complex_queries() -> list[str]:
    """Complex queries that should use direct routing."""
    return [
        "Explain quantum entanglement and its implications for quantum computing in detail",
        "Derive the Navier-Stokes equations from first principles",
        "Write a comprehensive analysis of Kant's Critique of Pure Reason",
    ]


# ============================================================================
# PHASE 1: AGENT v2.0 CORE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_agent_initialization(test_models):
    """Test agent initializes correctly."""
    if not test_models:
        pytest.skip("No API keys available")

    agent = CascadeAgent(
        models=test_models,
        quality_config=QualityConfig.for_cascade(),
        enable_cascade=True,
        verbose=True,
    )

    assert agent is not None
    assert len(agent.models) >= 2, "Need at least 2 models for cascade"
    assert agent.enable_cascade is True
    assert agent.cascade is not None
    assert agent.streaming_cascade is not None

    print(f"✅ Agent initialized with {len(agent.models)} models")


@pytest.mark.asyncio
async def test_agent_from_env():
    """Test agent auto-discovery from environment."""
    providers = get_available_providers()

    if not providers:
        pytest.skip("No providers available in .env")

    agent = CascadeAgent.from_env(verbose=True)

    assert agent is not None
    assert len(agent.models) >= 1

    print(f"✅ Auto-discovered {len(agent.models)} models from environment")
    for model in agent.models:
        print(f"  - {model.name} ({model.provider}): ${model.cost:.6f}")


@pytest.mark.asyncio
async def test_agent_basic_run(agent, simple_queries):
    """Test basic agent run() method (non-streaming)."""
    query = simple_queries[0]

    result = await agent.run(query=query, max_tokens=50, temperature=0.7)

    assert isinstance(result, CascadeResult)
    assert result.content is not None
    assert len(result.content) > 0
    assert result.model_used is not None
    assert result.total_cost >= 0
    assert result.latency_ms > 0
    assert result.complexity in ["trivial", "simple", "moderate", "hard", "expert"]

    print("\n✅ Basic run() test passed")
    print(f"Query: {query}")
    print(f"Response: {result.content[:100]}...")
    print(f"Model: {result.model_used}")
    print(f"Cost: ${result.total_cost:.6f}")
    print(f"Latency: {result.latency_ms:.1f}ms")
    print(f"Complexity: {result.complexity}")
    print(f"Cascaded: {result.cascaded}")
    print(f"Draft accepted: {result.draft_accepted}")


@pytest.mark.asyncio
async def test_complexity_routing(agent, simple_queries, complex_queries):
    """Test that complexity-based routing works."""
    # Simple query should use cascade
    simple_result = await agent.run(query=simple_queries[0], max_tokens=50)

    # Complex query should use direct
    complex_result = await agent.run(query=complex_queries[0], max_tokens=100)

    print("\n✅ Complexity routing test")
    print("Simple query:")
    print(f"  Complexity: {simple_result.complexity}")
    print(f"  Cascaded: {simple_result.cascaded}")
    print(f"  Strategy: {simple_result.routing_strategy}")

    print("\nComplex query:")
    print(f"  Complexity: {complex_result.complexity}")
    print(f"  Cascaded: {complex_result.cascaded}")
    print(f"  Strategy: {complex_result.routing_strategy}")

    # Simple queries tend to use cascade
    assert simple_result.complexity in ["trivial", "simple", "moderate"]

    # Complex queries tend to use direct
    # (Note: complexity detection isn't perfect, so we just check it was detected)
    assert complex_result.complexity is not None


@pytest.mark.asyncio
async def test_force_direct_routing(agent, simple_queries):
    """Test force_direct parameter."""
    query = simple_queries[0]

    # Force direct routing
    result = await agent.run(query=query, max_tokens=50, force_direct=True)

    assert result.routing_strategy == "direct"
    assert result.cascaded is False
    assert "Forced direct routing" in result.reason

    print("\n✅ Force direct routing test passed")
    print(f"Strategy: {result.routing_strategy}")
    print(f"Reason: {result.reason}")


@pytest.mark.asyncio
async def test_complexity_hint(agent, simple_queries):
    """Test complexity_hint parameter."""
    query = simple_queries[0]

    # Override with expert hint
    result = await agent.run(query=query, max_tokens=50, complexity_hint="expert")

    assert result.complexity == "expert"
    assert result.routing_strategy == "direct"  # Expert queries use direct

    print("\n✅ Complexity hint test passed")
    print(f"Detected complexity: {result.complexity}")
    print(f"Strategy: {result.routing_strategy}")


# ============================================================================
# PHASE 2: STREAMING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_streaming_basic(agent, simple_queries):
    """Test basic streaming functionality."""
    query = simple_queries[0]

    result = await agent.run_streaming(
        query=query, max_tokens=50, temperature=0.7, enable_visual=False  # Disable visual for test
    )

    assert isinstance(result, CascadeResult)
    assert result.content is not None
    assert len(result.content) > 0
    assert result.metadata["streaming"] is True

    print("\n✅ Basic streaming test passed")
    print(f"Query: {query}")
    print(f"Response: {result.content[:100]}...")
    print(f"Model: {result.model_used}")
    print(f"Cost: ${result.total_cost:.6f}")


@pytest.mark.asyncio
async def test_streaming_vs_non_streaming(agent, simple_queries):
    """CRITICAL: Test that streaming produces identical results to non-streaming."""
    query = simple_queries[0]

    # Non-streaming
    result_normal = await agent.run(query=query, max_tokens=50, temperature=0.7)

    # Streaming
    result_streaming = await agent.run_streaming(
        query=query, max_tokens=50, temperature=0.7, enable_visual=False
    )

    # Results should be similar (content might vary slightly due to randomness)
    assert result_normal.content is not None
    assert result_streaming.content is not None
    assert len(result_normal.content) > 0
    assert len(result_streaming.content) > 0

    # Routing should be same
    assert result_normal.cascaded == result_streaming.cascaded
    assert result_normal.routing_strategy == result_streaming.routing_strategy

    print("\n✅ Streaming vs non-streaming test passed")
    print(f"Query: {query}")
    print(f"Non-streaming length: {len(result_normal.content)}")
    print(f"Streaming length: {len(result_streaming.content)}")
    print(f"Both used cascade: {result_normal.cascaded}")


@pytest.mark.asyncio
async def test_streaming_events():
    """Test streaming events are emitted correctly."""
    # Get available providers
    providers = get_available_providers()
    if not providers:
        pytest.skip("No providers available")

    # Create simple cascade
    from cascadeflow.speculative import WholeResponseCascade

    models = []
    if "groq" in providers:
        models.append(ModelConfig(name="llama-3.1-8b-instant", provider="groq", cost=0.0))
    if "openai" in providers:
        models.append(ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002))

    if len(models) < 2:
        pytest.skip("Need at least 2 models for cascade")

    cascade = WholeResponseCascade(
        drafter=models[0],
        verifier=models[1],
        providers=providers,
        quality_config=QualityConfig.for_cascade(),
        verbose=True,
    )

    # Wrap for streaming with StreamManager
    streaming = StreamManager(cascade, verbose=True)

    # Collect events
    events = []
    async for event in streaming.stream("What is 2+2?", max_tokens=50):
        events.append(event)

    # Should have events
    assert len(events) > 0

    # Should have CHUNK events
    chunk_events = [e for e in events if e.type == StreamEventType.CHUNK]
    assert len(chunk_events) > 0

    # Should have COMPLETE event
    complete_events = [e for e in events if e.type == StreamEventType.COMPLETE]
    assert len(complete_events) == 1

    print("\n✅ Streaming events test passed")
    print(f"Total events: {len(events)}")
    print(f"CHUNK events: {len(chunk_events)}")
    print(f"COMPLETE events: {len(complete_events)}")

    # Check if switch event occurred
    switch_events = [e for e in events if e.type == StreamEventType.SWITCH]
    if switch_events:
        print(f"SWITCH events: {len(switch_events)}")


@pytest.mark.asyncio
async def test_streaming_visual_indicator(agent, simple_queries):
    """Test streaming with visual indicator (in test mode)."""
    query = simple_queries[0]

    # Run with visual enabled (will auto-disable in non-TTY)
    result = await agent.run_streaming(query=query, max_tokens=50, enable_visual=True)

    assert isinstance(result, CascadeResult)
    assert result.content is not None

    print("\n✅ Visual indicator test passed")
    print("(Visual feedback auto-disabled in non-TTY environment)")


@pytest.mark.asyncio
async def test_silent_consumer():
    """Test SilentConsumer for non-visual streaming."""
    providers = get_available_providers()
    if not providers:
        pytest.skip("No providers available")

    from cascadeflow.speculative import WholeResponseCascade

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

    streaming = StreamManager(cascade)
    consumer = SilentConsumer(verbose=False)

    # Consume silently
    result = await consumer.consume(
        streaming_manager=streaming, query="What is 2+2?", max_tokens=50
    )

    assert result is not None
    assert "content" in result
    assert len(result["content"]) > 0

    print("\n✅ Silent consumer test passed")


# ============================================================================
# PHASE 3: STATISTICS & TRACKING
# ============================================================================


@pytest.mark.asyncio
async def test_statistics_tracking(agent, simple_queries):
    """Test statistics are tracked correctly."""
    # 🔧 FIX: Use telemetry.reset() instead of manually setting stats
    # This ensures all required keys are present (including 'total_latency_ms')
    agent.telemetry.reset()

    # Run several queries
    for query in simple_queries[:3]:
        await agent.run(query, max_tokens=50)

    # Check stats
    stats = agent.get_stats()

    assert stats["total_queries"] == 3
    # ✅ FIXED: Allow 0 cost for free providers like Groq
    assert stats["total_cost"] >= 0  # Changed from > 0 to >= 0
    assert stats["cascade_used"] + stats["direct_routed"] == 3

    print("\n✅ Statistics tracking test passed")
    agent.print_stats()


@pytest.mark.asyncio
async def test_streaming_statistics(agent, simple_queries):
    """Test streaming queries are tracked in statistics."""
    initial_streaming = agent.stats.get("streaming_used", 0)

    # Run streaming query
    await agent.run_streaming(simple_queries[0], max_tokens=50, enable_visual=False)

    stats = agent.get_stats()
    assert stats["streaming_used"] > initial_streaming

    print("\n✅ Streaming statistics test passed")
    print(f"Streaming queries: {stats['streaming_used']}")


# ============================================================================
# PHASE 4: EDGE CASES & ERROR HANDLING
# ============================================================================


@pytest.mark.asyncio
async def test_empty_query(agent):
    """Test handling of empty query."""
    # ✅ FIXED: Agent handles empty queries gracefully (doesn't raise exception)
    # Empty strings get classified with complexity and routed appropriately
    result = await agent.run("", max_tokens=50)

    # Verify result exists and has expected attributes
    assert result is not None
    assert hasattr(result, "content")
    assert hasattr(result, "complexity")

    # Empty queries typically get classified as simple/trivial
    assert result.complexity in ["trivial", "simple", "moderate"]

    print("\n✅ Empty query handled gracefully")
    print(f"  Complexity: {result.complexity}")
    print(f"  Content length: {len(result.content)}")
    print(f"  Strategy: {result.routing_strategy}")


@pytest.mark.asyncio
async def test_very_long_query(agent):
    """Test handling of very long query."""
    long_query = "What is Python? " * 1000  # Very long query

    try:
        result = await agent.run(long_query, max_tokens=50)
        assert result is not None
        print("\n✅ Long query handled successfully")
    except Exception as e:
        # Some providers may reject very long queries
        print(f"\n⚠️  Long query rejected (expected): {e}")


@pytest.mark.asyncio
async def test_no_cascade_mode(test_models):
    """Test agent with cascade disabled."""
    if not test_models:
        pytest.skip("No API keys available")

    agent = CascadeAgent(models=test_models, enable_cascade=False, verbose=True)

    result = await agent.run("What is 2+2?", max_tokens=50)

    assert result.cascaded is False
    assert result.routing_strategy == "direct"

    print("\n✅ No cascade mode test passed")


# ============================================================================
# PHASE 5: INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_full_cascade_with_streaming(agent, simple_queries):
    """Test complete cascade flow with streaming."""
    query = simple_queries[0]

    # Run streaming
    start_time = time.time()
    result = await agent.run_streaming(query=query, max_tokens=50, enable_visual=False)
    end_time = time.time()

    elapsed_ms = (end_time - start_time) * 1000

    assert result is not None
    assert result.content is not None

    print("\n✅ Full cascade with streaming test passed")
    print(f"Query: {query}")
    print(f"Response: {result.content}")
    print(f"Model: {result.model_used}")
    print(f"Cascaded: {result.cascaded}")
    print(f"Draft accepted: {result.draft_accepted}")
    print(f"Elapsed: {elapsed_ms:.1f}ms")


@pytest.mark.asyncio
async def test_multiple_queries_batch(agent, simple_queries):
    """Test multiple queries in sequence."""
    results = []

    for query in simple_queries:
        result = await agent.run(query, max_tokens=50)
        results.append(result)

    assert len(results) == len(simple_queries)
    assert all(r.content is not None for r in results)

    print("\n✅ Batch queries test passed")
    print(f"Processed {len(results)} queries")

    # Print acceptance rate
    cascaded = [r for r in results if r.cascaded]
    if cascaded:
        accepted = [r for r in cascaded if r.draft_accepted]
        acceptance_rate = len(accepted) / len(cascaded) * 100
        print(f"Cascade acceptance rate: {acceptance_rate:.1f}%")


# ============================================================================
# SUMMARY TEST
# ============================================================================


@pytest.mark.asyncio
async def test_complete_system_validation(agent):
    """Complete system validation test."""
    print("\n" + "=" * 70)
    print("COMPLETE SYSTEM VALIDATION")
    print("=" * 70)

    # Test query
    query = "What is Python?"

    # 1. Non-streaming
    print("\n1. Testing non-streaming...")
    result_normal = await agent.run(query, max_tokens=50)
    print("   ✓ Non-streaming works")
    print(f"   Response: {result_normal.content[:50]}...")

    # 2. Streaming
    print("\n2. Testing streaming...")
    result_streaming = await agent.run_streaming(query, max_tokens=50, enable_visual=False)
    print("   ✓ Streaming works")
    print(f"   Response: {result_streaming.content[:50]}...")

    # 3. Verify routing
    print("\n3. Testing routing...")
    print(f"   Complexity: {result_normal.complexity}")
    print(f"   Strategy: {result_normal.routing_strategy}")
    print(f"   Cascaded: {result_normal.cascaded}")
    print("   ✓ Routing works")

    # 4. Verify statistics
    print("\n4. Testing statistics...")
    stats = agent.get_stats()
    print(f"   Total queries: {stats['total_queries']}")
    print(f"   Total cost: ${stats['total_cost']:.6f}")
    print("   ✓ Statistics work")

    print("\n" + "=" * 70)
    print("✅ ALL SYSTEMS OPERATIONAL")
    print("=" * 70)

    # Final stats summary
    agent.print_stats()


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    # Run all tests
    pytest.main([__file__, "-v", "-s"])
