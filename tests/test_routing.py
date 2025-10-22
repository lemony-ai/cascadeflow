"""
Test suite for routing module (Phase 2 Part A).

Tests:
1. RoutingStrategy enum
2. RoutingDecision dataclass
3. PreRouter routing logic
4. PreRouter statistics
5. ConditionalRouter
6. RouterChain
7. Integration with ComplexityDetector

Run:
    pytest tests/test_routing.py -v
    pytest tests/test_routing.py::test_routing_decision -v
"""

import pytest

from cascadeflow.quality.complexity import ComplexityDetector, QueryComplexity
from cascadeflow.routing import (
    ConditionalRouter,
    PreRouter,
    RouterChain,
    RoutingDecision,
    RoutingStrategy,
)

# ============================================================================
# TEST ROUTING STRATEGY ENUM
# ============================================================================


def test_routing_strategy_enum():
    """Test RoutingStrategy enum values."""
    assert RoutingStrategy.DIRECT_CHEAP.value == "direct_cheap"
    assert RoutingStrategy.DIRECT_BEST.value == "direct_best"
    assert RoutingStrategy.CASCADE.value == "cascade"
    assert RoutingStrategy.PARALLEL.value == "parallel"

    # Test all strategies exist
    strategies = [e.value for e in RoutingStrategy]
    assert "direct_cheap" in strategies
    assert "direct_best" in strategies
    assert "cascade" in strategies
    assert "parallel" in strategies


# ============================================================================
# TEST ROUTING DECISION
# ============================================================================


def test_routing_decision_creation():
    """Test RoutingDecision creation."""
    decision = RoutingDecision(
        strategy=RoutingStrategy.CASCADE,
        reason="Test routing",
        confidence=0.85,
        metadata={"test": True},
    )

    assert decision.strategy == RoutingStrategy.CASCADE
    assert decision.reason == "Test routing"
    assert decision.confidence == 0.85
    assert decision.metadata == {"test": True}
    assert decision.model_name is None
    assert decision.max_cost is None
    assert decision.min_quality is None


def test_routing_decision_validation():
    """Test RoutingDecision confidence validation."""
    # Valid confidence
    decision = RoutingDecision(
        strategy=RoutingStrategy.CASCADE, reason="Valid", confidence=0.5, metadata={}
    )
    assert decision.confidence == 0.5

    # Invalid confidence - should raise
    with pytest.raises(ValueError, match="Confidence must be 0-1"):
        RoutingDecision(
            strategy=RoutingStrategy.CASCADE, reason="Invalid", confidence=1.5, metadata={}
        )

    with pytest.raises(ValueError, match="Confidence must be 0-1"):
        RoutingDecision(
            strategy=RoutingStrategy.CASCADE, reason="Invalid", confidence=-0.1, metadata={}
        )


def test_routing_decision_is_direct():
    """Test is_direct() method."""
    decision_direct_best = RoutingDecision(
        strategy=RoutingStrategy.DIRECT_BEST, reason="Test", confidence=1.0, metadata={}
    )
    assert decision_direct_best.is_direct() is True
    assert decision_direct_best.is_cascade() is False

    decision_direct_cheap = RoutingDecision(
        strategy=RoutingStrategy.DIRECT_CHEAP, reason="Test", confidence=1.0, metadata={}
    )
    assert decision_direct_cheap.is_direct() is True
    assert decision_direct_cheap.is_cascade() is False


def test_routing_decision_is_cascade():
    """Test is_cascade() method."""
    decision = RoutingDecision(
        strategy=RoutingStrategy.CASCADE, reason="Test", confidence=0.8, metadata={}
    )
    assert decision.is_cascade() is True
    assert decision.is_direct() is False


# ============================================================================
# TEST PREROUTER
# ============================================================================


@pytest.mark.asyncio
async def test_prerouter_initialization():
    """Test PreRouter initialization."""
    router = PreRouter(enable_cascade=True, verbose=False)

    assert router.enable_cascade is True
    assert router.verbose is False
    assert router.detector is not None
    assert router.cascade_complexities == [
        QueryComplexity.TRIVIAL,
        QueryComplexity.SIMPLE,
        QueryComplexity.MODERATE,
    ]


@pytest.mark.asyncio
async def test_prerouter_simple_query_routes_to_cascade():
    """Test PreRouter routes simple queries to cascade."""
    router = PreRouter(enable_cascade=True, verbose=False)

    # Simple query
    decision = await router.route("What is 2+2?", context={"complexity": QueryComplexity.SIMPLE})

    assert decision.strategy == RoutingStrategy.CASCADE
    assert decision.is_cascade() is True
    assert "simple" in decision.reason.lower()
    assert 0 <= decision.confidence <= 1
    assert decision.metadata["complexity"] == "simple"
    assert decision.metadata["router"] == "pre"
    assert decision.metadata["router_type"] == "complexity_based"


@pytest.mark.asyncio
async def test_prerouter_hard_query_routes_to_direct():
    """Test PreRouter routes hard queries to direct best."""
    router = PreRouter(enable_cascade=True, verbose=False)

    # Hard query
    decision = await router.route(
        "Explain quantum entanglement in detail", context={"complexity": QueryComplexity.HARD}
    )

    assert decision.strategy == RoutingStrategy.DIRECT_BEST
    assert decision.is_direct() is True
    assert "hard" in decision.reason.lower()
    assert decision.metadata["complexity"] == "hard"


@pytest.mark.asyncio
async def test_prerouter_expert_query_routes_to_direct():
    """Test PreRouter routes expert queries to direct best."""
    router = PreRouter(enable_cascade=True, verbose=False)

    # Expert query
    decision = await router.route(
        "Derive the Navier-Stokes equations", context={"complexity": QueryComplexity.EXPERT}
    )

    assert decision.strategy == RoutingStrategy.DIRECT_BEST
    assert decision.is_direct() is True
    assert "expert" in decision.reason.lower()


@pytest.mark.asyncio
async def test_prerouter_moderate_query_routes_to_cascade():
    """Test PreRouter routes moderate queries to cascade."""
    router = PreRouter(enable_cascade=True, verbose=False)

    decision = await router.route(
        "Summarize the key points of this article", context={"complexity": QueryComplexity.MODERATE}
    )

    assert decision.strategy == RoutingStrategy.CASCADE
    assert decision.is_cascade() is True
    assert "moderate" in decision.reason.lower()


@pytest.mark.asyncio
async def test_prerouter_trivial_query_routes_to_cascade():
    """Test PreRouter routes trivial queries to cascade."""
    router = PreRouter(enable_cascade=True, verbose=False)

    decision = await router.route("Hello", context={"complexity": QueryComplexity.TRIVIAL})

    assert decision.strategy == RoutingStrategy.CASCADE
    assert decision.is_cascade() is True


@pytest.mark.asyncio
async def test_prerouter_force_direct():
    """Test PreRouter force_direct context option."""
    router = PreRouter(enable_cascade=True, verbose=False)

    # Even simple query should route to direct if forced
    decision = await router.route(
        "What is 2+2?", context={"complexity": QueryComplexity.SIMPLE, "force_direct": True}
    )

    assert decision.strategy == RoutingStrategy.DIRECT_BEST
    assert decision.is_direct() is True
    assert "forced" in decision.reason.lower()
    assert decision.metadata["force_direct"] is True


@pytest.mark.asyncio
async def test_prerouter_cascade_disabled():
    """Test PreRouter with cascade disabled."""
    router = PreRouter(enable_cascade=False, verbose=False)

    # Even simple query should route to direct when cascade disabled
    decision = await router.route("What is 2+2?", context={"complexity": QueryComplexity.SIMPLE})

    assert decision.strategy == RoutingStrategy.DIRECT_BEST
    assert decision.is_direct() is True
    assert "cascade disabled" in decision.reason.lower()


@pytest.mark.asyncio
async def test_prerouter_auto_complexity_detection():
    """Test PreRouter auto-detects complexity when not provided."""
    router = PreRouter(enable_cascade=True, verbose=False)

    # Simple query without context
    decision = await router.route("What is 2+2?")

    assert decision.strategy in [RoutingStrategy.CASCADE, RoutingStrategy.DIRECT_BEST]
    assert 0 <= decision.confidence <= 1
    assert "complexity" in decision.metadata
    assert decision.metadata["complexity"] in [c.value for c in QueryComplexity]


@pytest.mark.asyncio
async def test_prerouter_complexity_hint():
    """Test PreRouter with complexity_hint in context."""
    router = PreRouter(enable_cascade=True, verbose=False)

    decision = await router.route("What is AI?", context={"complexity_hint": "hard"})

    assert decision.strategy == RoutingStrategy.DIRECT_BEST
    assert decision.metadata["complexity"] == "hard"


# ============================================================================
# TEST PREROUTER STATISTICS
# ============================================================================


@pytest.mark.asyncio
async def test_prerouter_statistics_tracking():
    """Test PreRouter tracks statistics correctly."""
    router = PreRouter(enable_cascade=True, verbose=False)

    # Route several queries
    await router.route("Simple 1", context={"complexity": QueryComplexity.SIMPLE})
    await router.route("Simple 2", context={"complexity": QueryComplexity.SIMPLE})
    await router.route("Hard", context={"complexity": QueryComplexity.HARD})
    await router.route("Expert", context={"complexity": QueryComplexity.EXPERT})

    stats = router.get_stats()

    assert stats["total_queries"] == 4
    assert stats["by_complexity"]["simple"] == 2
    assert stats["by_complexity"]["hard"] == 1
    assert stats["by_complexity"]["expert"] == 1
    assert stats["by_strategy"]["cascade"] == 2
    assert stats["by_strategy"]["direct_best"] == 2


@pytest.mark.asyncio
async def test_prerouter_statistics_empty():
    """Test PreRouter stats when no queries routed."""
    router = PreRouter(enable_cascade=True, verbose=False)

    stats = router.get_stats()

    assert stats["total_queries"] == 0
    assert "message" in stats


@pytest.mark.asyncio
async def test_prerouter_reset_stats():
    """Test PreRouter reset_stats() method."""
    router = PreRouter(enable_cascade=True, verbose=False)

    # Route some queries
    await router.route("Test 1", context={"complexity": QueryComplexity.SIMPLE})
    await router.route("Test 2", context={"complexity": QueryComplexity.HARD})

    stats_before = router.get_stats()
    assert stats_before["total_queries"] == 2

    # Reset stats
    router.reset_stats()

    stats_after = router.get_stats()
    assert stats_after["total_queries"] == 0


@pytest.mark.asyncio
async def test_prerouter_forced_direct_stats():
    """Test PreRouter tracks forced direct in stats."""
    router = PreRouter(enable_cascade=True, verbose=False)

    # Force direct twice
    await router.route("Q1", context={"force_direct": True})
    await router.route("Q2", context={"force_direct": True})

    stats = router.get_stats()
    assert stats["forced_direct"] == 2


# ============================================================================
# TEST CONDITIONAL ROUTER
# ============================================================================


@pytest.mark.asyncio
async def test_conditional_router_simple_condition():
    """Test ConditionalRouter with simple conditions."""
    router = ConditionalRouter(
        conditions=[
            (lambda q, ctx: len(q) < 10, RoutingStrategy.DIRECT_CHEAP),
            (lambda q, ctx: "urgent" in q.lower(), RoutingStrategy.DIRECT_BEST),
        ],
        default=RoutingStrategy.CASCADE,
    )

    # Short query → DIRECT_CHEAP
    decision = await router.route("Hi")
    assert decision.strategy == RoutingStrategy.DIRECT_CHEAP

    # Query with 'urgent' → DIRECT_BEST
    decision = await router.route("This is urgent and important")
    assert decision.strategy == RoutingStrategy.DIRECT_BEST

    # Normal query → CASCADE (default)
    decision = await router.route("What is the weather today?")
    assert decision.strategy == RoutingStrategy.CASCADE


@pytest.mark.asyncio
async def test_conditional_router_first_match_wins():
    """Test ConditionalRouter uses first matching condition."""
    router = ConditionalRouter(
        conditions=[
            (lambda q, ctx: len(q) < 10, RoutingStrategy.DIRECT_CHEAP),
            (lambda q, ctx: len(q) < 20, RoutingStrategy.CASCADE),
        ],
        default=RoutingStrategy.DIRECT_BEST,
    )

    # Short query matches first condition
    decision = await router.route("Hi")
    assert decision.strategy == RoutingStrategy.DIRECT_CHEAP

    # Medium query matches second condition
    decision = await router.route("What is the time?")
    assert decision.strategy == RoutingStrategy.CASCADE


@pytest.mark.asyncio
async def test_conditional_router_stats():
    """Test ConditionalRouter tracks statistics."""
    router = ConditionalRouter(
        conditions=[
            (lambda q, ctx: len(q) < 5, RoutingStrategy.DIRECT_CHEAP),
        ],
        default=RoutingStrategy.CASCADE,
    )

    await router.route("Hi")
    await router.route("What is AI?")
    await router.route("Hello there friend")

    stats = router.get_stats()
    assert stats["direct_cheap"] == 1
    assert stats["cascade"] == 2


# ============================================================================
# TEST ROUTER CHAIN
# ============================================================================


@pytest.mark.asyncio
async def test_router_chain():
    """Test RouterChain with multiple routers."""
    # First router: only routes if query has "urgent"
    router1 = ConditionalRouter(
        conditions=[
            (lambda q, ctx: "urgent" in q.lower(), RoutingStrategy.DIRECT_BEST),
        ],
        default=RoutingStrategy.CASCADE,
    )

    # Second router: complexity-based
    router2 = PreRouter(enable_cascade=True)

    chain = RouterChain([router1, router2])

    # Urgent query → router1 decides
    decision = await chain.route("URGENT: Fix this bug!")
    assert decision.strategy == RoutingStrategy.DIRECT_BEST

    # Normal query → passes through to router2
    decision = await chain.route("What is AI?", context={"complexity": QueryComplexity.SIMPLE})
    assert decision.strategy == RoutingStrategy.CASCADE


# ============================================================================
# TEST INTEGRATION WITH COMPLEXITY DETECTOR
# ============================================================================


@pytest.mark.asyncio
async def test_prerouter_with_custom_complexity_detector():
    """Test PreRouter with custom ComplexityDetector."""
    detector = ComplexityDetector()
    router = PreRouter(enable_cascade=True, complexity_detector=detector, verbose=False)

    # Should use the custom detector
    decision = await router.route("What is 2+2?")
    assert decision.strategy in [RoutingStrategy.CASCADE, RoutingStrategy.DIRECT_BEST]
    assert "complexity" in decision.metadata


@pytest.mark.asyncio
async def test_prerouter_custom_cascade_complexities():
    """Test PreRouter with custom cascade complexity levels."""
    # Only TRIVIAL uses cascade
    router = PreRouter(
        enable_cascade=True, cascade_complexities=[QueryComplexity.TRIVIAL], verbose=False
    )

    # TRIVIAL → CASCADE
    decision = await router.route("Hi", context={"complexity": QueryComplexity.TRIVIAL})
    assert decision.strategy == RoutingStrategy.CASCADE

    # SIMPLE → DIRECT (not in cascade list)
    decision = await router.route("What is 2+2?", context={"complexity": QueryComplexity.SIMPLE})
    assert decision.strategy == RoutingStrategy.DIRECT_BEST


# ============================================================================
# TEST ERROR HANDLING
# ============================================================================


@pytest.mark.asyncio
async def test_prerouter_invalid_complexity_hint():
    """Test PreRouter handles invalid complexity hint gracefully."""
    router = PreRouter(enable_cascade=True, verbose=False)

    # Invalid hint should trigger auto-detection
    decision = await router.route("What is AI?", context={"complexity_hint": "invalid_level"})

    # Should still route successfully
    assert decision.strategy in [RoutingStrategy.CASCADE, RoutingStrategy.DIRECT_BEST]
    assert "complexity" in decision.metadata


@pytest.mark.asyncio
async def test_conditional_router_exception_in_condition():
    """Test ConditionalRouter handles exceptions in conditions."""

    def bad_condition(q, ctx):
        raise ValueError("Test error")

    router = ConditionalRouter(
        conditions=[
            (bad_condition, RoutingStrategy.DIRECT_BEST),
        ],
        default=RoutingStrategy.CASCADE,
    )

    # Should use default when condition fails
    decision = await router.route("Test query")
    assert decision.strategy == RoutingStrategy.CASCADE


# ============================================================================
# TEST PRINT STATS (Output Verification)
# ============================================================================


@pytest.mark.asyncio
async def test_prerouter_print_stats(capsys):
    """Test PreRouter print_stats() outputs correctly."""
    router = PreRouter(enable_cascade=True, verbose=False)

    # Route some queries
    await router.route("Simple", context={"complexity": QueryComplexity.SIMPLE})
    await router.route("Hard", context={"complexity": QueryComplexity.HARD})

    # Print stats
    router.print_stats()

    # Capture output
    captured = capsys.readouterr()

    assert "PRE-ROUTER STATISTICS" in captured.out
    assert "Total Queries Routed: 2" in captured.out
    assert "BY COMPLEXITY:" in captured.out
    assert "BY STRATEGY:" in captured.out


@pytest.mark.asyncio
async def test_prerouter_print_stats_empty(capsys):
    """Test PreRouter print_stats() when no queries."""
    router = PreRouter(enable_cascade=True, verbose=False)

    router.print_stats()

    captured = capsys.readouterr()
    assert "No routing statistics available" in captured.out


# ============================================================================
# INTEGRATION TEST WITH MOCK AGENT
# ============================================================================


@pytest.mark.asyncio
async def test_prerouter_integration_flow():
    """Test complete routing flow as it would be used in agent."""
    router = PreRouter(enable_cascade=True, verbose=False)

    queries_and_expected = [
        ("What is 2+2?", QueryComplexity.SIMPLE, RoutingStrategy.CASCADE),
        ("Hi", QueryComplexity.TRIVIAL, RoutingStrategy.CASCADE),
        ("Explain quantum mechanics", QueryComplexity.HARD, RoutingStrategy.DIRECT_BEST),
        ("Derive Schrödinger equation", QueryComplexity.EXPERT, RoutingStrategy.DIRECT_BEST),
    ]

    for query, complexity, expected_strategy in queries_and_expected:
        decision = await router.route(query, context={"complexity": complexity})

        assert decision.strategy == expected_strategy
        assert decision.confidence > 0
        assert "complexity" in decision.metadata
        assert decision.metadata["router"] == "pre"


# ============================================================================
# PERFORMANCE TEST
# ============================================================================


@pytest.mark.asyncio
async def test_prerouter_performance():
    """Test PreRouter performance with multiple queries."""
    import time

    router = PreRouter(enable_cascade=True, verbose=False)

    start = time.time()

    # Route 100 queries
    for i in range(100):
        await router.route(f"Query {i}", context={"complexity": QueryComplexity.SIMPLE})

    elapsed = time.time() - start

    # Should route 100 queries in less than 1 second
    assert elapsed < 1.0

    stats = router.get_stats()
    assert stats["total_queries"] == 100


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
