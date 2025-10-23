"""
Phase 2.1: Cascade Integration Testing with Logprobs + Statistics

UPDATED: October 2025 with current model names and comprehensive stats tracking

Tests the TokenLevelSpeculativeCascade with Anthropic + OpenAI providers.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import pytest

# Import cascade components
from cascadeflow.config import ModelConfig
from cascadeflow.speculative import (
    DeferralStrategy,
    FlexibleDeferralRule,
    SpeculativeResult,
    TokenLevelSpeculativeCascade,
)

from cascadeflow.providers import PROVIDER_REGISTRY

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================
# STATISTICS TRACKING
# ==========================================


@dataclass
class TestStats:
    """Track statistics across all tests."""

    total_queries: int = 0
    total_cost: float = 0.0
    total_cost_saved: float = 0.0
    total_tokens_drafted: int = 0
    total_tokens_accepted: int = 0
    total_speedup: float = 0.0
    acceptance_rates: list[float] = None

    def __post_init__(self):
        if self.acceptance_rates is None:
            self.acceptance_rates = []

    def add_result(self, result: SpeculativeResult):
        """Add a result to statistics."""
        self.total_queries += 1
        self.total_cost += result.total_cost
        self.total_cost_saved += result.metadata.get("cost_saved", 0.0)
        self.total_tokens_drafted += result.tokens_drafted
        self.total_tokens_accepted += result.tokens_accepted
        self.total_speedup += result.speedup
        self.acceptance_rates.append(result.acceptance_rate)

    def get_summary(self) -> dict[str, Any]:
        """Get statistics summary."""
        if self.total_queries == 0:
            return {}

        return {
            "total_queries": self.total_queries,
            "total_cost": self.total_cost,
            "total_cost_saved": self.total_cost_saved,
            "avg_cost_per_query": self.total_cost / self.total_queries,
            "total_tokens_drafted": self.total_tokens_drafted,
            "total_tokens_accepted": self.total_tokens_accepted,
            "overall_acceptance_rate": (
                self.total_tokens_accepted / self.total_tokens_drafted
                if self.total_tokens_drafted > 0
                else 0
            ),
            "avg_acceptance_rate": sum(self.acceptance_rates) / len(self.acceptance_rates),
            "min_acceptance_rate": min(self.acceptance_rates) if self.acceptance_rates else 0,
            "max_acceptance_rate": max(self.acceptance_rates) if self.acceptance_rates else 0,
            "avg_speedup": self.total_speedup / self.total_queries,
        }

    def print_summary(self):
        """Print beautiful statistics summary."""
        summary = self.get_summary()
        if not summary:
            return

        print("\n" + "=" * 70)
        print("📊 PHASE 2.1 STATISTICS SUMMARY")
        print("=" * 70)
        print(f"Total Queries:              {summary['total_queries']}")
        print(f"Total Cost:                 ${summary['total_cost']:.6f}")
        print(f"Total Cost Saved:           ${summary['total_cost_saved']:.6f}")
        print(f"Avg Cost Per Query:         ${summary['avg_cost_per_query']:.6f}")
        print("")
        print(f"Total Tokens Drafted:       {summary['total_tokens_drafted']}")
        print(f"Total Tokens Accepted:      {summary['total_tokens_accepted']}")
        print(f"Overall Acceptance Rate:    {summary['overall_acceptance_rate']:.1%}")
        print("")
        print(f"Average Acceptance Rate:    {summary['avg_acceptance_rate']:.1%}")
        print(f"Min Acceptance Rate:        {summary['min_acceptance_rate']:.1%}")
        print(f"Max Acceptance Rate:        {summary['max_acceptance_rate']:.1%}")
        print("")
        print(f"Average Speedup:            {summary['avg_speedup']:.2f}x")
        print("")
        print(
            f"💰 Cost Efficiency:         {(summary['total_cost_saved']/summary['total_cost']*100):.1f}% saved"
        )
        print("=" * 70 + "\n")


# Global stats tracker
test_stats = TestStats()


def print_result_stats(result: SpeculativeResult, test_name: str):
    """Print detailed statistics for a single result."""
    print(f"\n{'─'*60}")
    print(f"📈 {test_name} - DETAILED STATS")
    print(f"{'─'*60}")
    print(f"Content Length:         {len(result.content)} chars")
    print(f"Tokens Drafted:         {result.tokens_drafted}")
    print(f"Tokens Accepted:        {result.tokens_accepted}")
    print(f"Tokens Deferred:        {result.tokens_deferred}")
    print(f"Acceptance Rate:        {result.acceptance_rate:.1%}")
    print("")
    print(f"Cost:                   ${result.total_cost:.6f}")
    print(f"Cost Saved:             ${result.metadata.get('cost_saved', 0):.6f}")
    print(f"Sequential Cost:        ${result.metadata.get('sequential_cost', 0):.6f}")
    print("")
    print(f"Latency:                {result.latency_ms:.0f}ms")
    print(f"Speedup:                {result.speedup:.2f}x")
    print("")
    print(f"Strategy:               {result.deferral_strategy}")
    print(f"Chunks Processed:       {result.chunks_processed}")
    print(f"Deferral Decisions:     {result.metadata.get('deferral_decisions', 0)}")
    print(f"{'─'*60}\n")


# ==========================================
# FIXTURES - UPDATED MODEL NAMES
# ==========================================


@pytest.fixture
def providers() -> dict[str, Any]:
    """Initialize Anthropic and OpenAI providers."""
    providers_dict = {}

    if os.getenv("ANTHROPIC_API_KEY"):
        providers_dict["anthropic"] = PROVIDER_REGISTRY["anthropic"]()
        logger.info("✓ Anthropic provider initialized")
    else:
        pytest.skip("ANTHROPIC_API_KEY not set")

    if os.getenv("OPENAI_API_KEY"):
        providers_dict["openai"] = PROVIDER_REGISTRY["openai"]()
        logger.info("✓ OpenAI provider initialized")
    else:
        pytest.skip("OPENAI_API_KEY not set")

    return providers_dict


@pytest.fixture
def anthropic_drafter() -> ModelConfig:
    """Anthropic Haiku as drafter (fast, cheap)."""
    return ModelConfig(
        name="claude-3-5-haiku-20241022",  # Updated to latest Haiku
        provider="anthropic",
        cost=0.00025,  # $0.25 per 1M input tokens
        speed_ms=300,
        quality_score=0.75,
        domains=["general"],
    )


@pytest.fixture
def openai_verifier() -> ModelConfig:
    """OpenAI GPT-4o Mini as verifier (good balance)."""
    return ModelConfig(
        name="gpt-4o-mini",  # Updated to current model
        provider="openai",
        cost=0.00015,  # $0.15 per 1M input tokens
        speed_ms=600,
        quality_score=0.82,
        domains=["general"],
    )


@pytest.fixture
def openai_drafter() -> ModelConfig:
    """OpenAI GPT-4o Mini as drafter."""
    return ModelConfig(
        name="gpt-4o-mini",
        provider="openai",
        cost=0.00015,
        speed_ms=600,
        quality_score=0.80,
        domains=["general"],
    )


@pytest.fixture
def anthropic_verifier() -> ModelConfig:
    """Anthropic Sonnet as verifier (higher quality)."""
    return ModelConfig(
        name="claude-sonnet-4",  # Updated to Claude 4
        provider="anthropic",
        cost=0.003,
        speed_ms=1000,
        quality_score=0.92,
        domains=["general"],
    )


# ==========================================
# PHASE 2.1: BASIC CASCADE TESTS
# ==========================================


@pytest.mark.asyncio
async def test_basic_cascade_execution(providers, anthropic_drafter, openai_verifier):
    """Test 1: Basic cascade execution works end-to-end."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: Basic Cascade Execution")
    logger.info("=" * 60)

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        chunk_size=10,
        verbose=True,
    )

    query = "What is 2+2? Give a brief answer."

    result = await cascade.execute(query=query, max_tokens=50, temperature=0.7)

    # Assertions
    assert isinstance(result, SpeculativeResult)
    assert result.content, "Response should have content"
    assert result.tokens_drafted > 0, "Should have drafted tokens"
    assert result.drafter_model == anthropic_drafter.name
    assert result.verifier_model == openai_verifier.name

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 1")

    logger.info(f"✓ Content: {result.content[:100]}...")
    logger.info("✓ Test 1 PASSED")


@pytest.mark.asyncio
async def test_logprobs_flow_through_cascade(providers, anthropic_drafter, openai_verifier):
    """Test 2: Verify logprobs flow through drafter and verifier."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Logprobs Flow")
    logger.info("=" * 60)

    deferral_rule = FlexibleDeferralRule(
        strategy=DeferralStrategy.COMPARATIVE, confidence_threshold=0.7
    )

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        deferral_rule=deferral_rule,
        chunk_size=10,
        verbose=True,
    )

    query = "Explain what logprobs are in one sentence."

    result = await cascade.execute(query=query, max_tokens=30, temperature=0.7)

    # Check deferral decisions were logged
    assert len(deferral_rule.decision_log) > 0, "Should have deferral decisions"

    # Verify decision log structure
    first_decision = deferral_rule.decision_log[0]
    assert "position" in first_decision
    assert "draft_token" in first_decision
    assert "draft_prob" in first_decision
    assert "deferred" in first_decision
    assert "reason" in first_decision

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 2")

    logger.info(f"✓ Deferral decisions logged: {len(deferral_rule.decision_log)}")
    logger.info("✓ Test 2 PASSED")


@pytest.mark.asyncio
async def test_metrics_calculation(providers, anthropic_drafter, openai_verifier):
    """Test 3: Verify all metrics are calculated correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Metrics Calculation")
    logger.info("=" * 60)

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        chunk_size=10,
        verbose=True,
    )

    query = "List 3 primary colors."

    result = await cascade.execute(query=query, max_tokens=30, temperature=0.5)

    # Verify metrics
    assert 0 <= result.acceptance_rate <= 1.0, "Acceptance rate should be 0-100%"
    assert result.speedup >= 0, "Speedup should be non-negative"
    assert result.total_cost >= 0, "Cost should be non-negative"
    assert result.latency_ms > 0, "Latency should be positive"
    assert result.chunks_processed > 0, "Should process at least one chunk"

    # Verify metadata
    assert "cost_saved" in result.metadata
    assert "sequential_cost" in result.metadata
    assert "deferral_decisions" in result.metadata

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 3")

    logger.info("✓ All metrics validated")
    logger.info("✓ Test 3 PASSED")


# ==========================================
# PHASE 2.2: DEFERRAL STRATEGY TESTS
# ==========================================


@pytest.mark.asyncio
async def test_confidence_threshold_strategy(providers, anthropic_drafter, openai_verifier):
    """Test 4: CONFIDENCE_THRESHOLD strategy."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: CONFIDENCE_THRESHOLD Strategy")
    logger.info("=" * 60)

    deferral_rule = FlexibleDeferralRule(
        strategy=DeferralStrategy.CONFIDENCE_THRESHOLD, confidence_threshold=0.7
    )

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        deferral_rule=deferral_rule,
        chunk_size=15,
        verbose=True,
    )

    query = "What is the capital of France?"

    result = await cascade.execute(query=query, max_tokens=20, temperature=0.3)

    assert result.deferral_strategy == "confidence"
    assert result.acceptance_rate >= 0, "Should have acceptance rate"

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 4 - CONFIDENCE_THRESHOLD")

    logger.info("✓ Test 4 PASSED")


@pytest.mark.asyncio
async def test_comparative_strategy(providers, anthropic_drafter, openai_verifier):
    """Test 5: COMPARATIVE strategy."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: COMPARATIVE Strategy")
    logger.info("=" * 60)

    deferral_rule = FlexibleDeferralRule(
        strategy=DeferralStrategy.COMPARATIVE, comparative_delta=0.15
    )

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        deferral_rule=deferral_rule,
        chunk_size=10,
        verbose=True,
    )

    query = "Explain quantum computing briefly."

    result = await cascade.execute(query=query, max_tokens=40, temperature=0.7)

    assert result.deferral_strategy == "comparative"

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 5 - COMPARATIVE")

    logger.info("✓ Test 5 PASSED")


@pytest.mark.asyncio
async def test_token_list_strategy(providers, anthropic_drafter, openai_verifier):
    """Test 6: TOKEN_LIST strategy."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: TOKEN_LIST Strategy")
    logger.info("=" * 60)

    deferral_rule = FlexibleDeferralRule(
        strategy=DeferralStrategy.TOKEN_LIST, top_k=10, min_probability=0.01
    )

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        deferral_rule=deferral_rule,
        chunk_size=12,
        verbose=True,
    )

    query = "Write a haiku about AI."

    result = await cascade.execute(query=query, max_tokens=30, temperature=0.8)

    assert result.deferral_strategy == "token_list"

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 6 - TOKEN_LIST")

    logger.info("✓ Test 6 PASSED")


# ==========================================
# PHASE 2.3: INTEGRATION TEST SUITE
# ==========================================


@pytest.mark.asyncio
async def test_simple_factual_query(providers, anthropic_drafter, openai_verifier):
    """Test 7: Simple factual query (expect high acceptance)."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 7: Simple Factual Query")
    logger.info("=" * 60)

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        chunk_size=10,
        verbose=True,
    )

    query = "What is the boiling point of water at sea level?"

    result = await cascade.execute(query=query, max_tokens=30, temperature=0.3)

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 7 - Simple Factual")

    logger.info("✓ Query type: Simple factual")
    logger.info("✓ Test 7 PASSED")


@pytest.mark.asyncio
async def test_complex_reasoning_query(providers, anthropic_drafter, openai_verifier):
    """Test 8: Complex reasoning query (expect lower acceptance)."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 8: Complex Reasoning Query")
    logger.info("=" * 60)

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        chunk_size=10,
        verbose=True,
    )

    query = "Explain the philosophical implications of Gödel's incompleteness theorems."

    result = await cascade.execute(query=query, max_tokens=60, temperature=0.7)

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 8 - Complex Reasoning")

    logger.info("✓ Query type: Complex reasoning")
    logger.info("✓ Test 8 PASSED")


@pytest.mark.asyncio
async def test_creative_writing_query(providers, anthropic_drafter, openai_verifier):
    """Test 9: Creative writing query (expect medium acceptance)."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 9: Creative Writing Query")
    logger.info("=" * 60)

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        chunk_size=15,
        verbose=True,
    )

    query = "Write a short poem about the ocean."

    result = await cascade.execute(query=query, max_tokens=50, temperature=0.8)

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 9 - Creative Writing")

    logger.info("✓ Query type: Creative writing")
    logger.info("✓ Test 9 PASSED")


@pytest.mark.asyncio
async def test_code_generation_query(providers, anthropic_drafter, openai_verifier):
    """Test 10: Code generation query."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 10: Code Generation Query")
    logger.info("=" * 60)

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        chunk_size=15,
        verbose=True,
    )

    query = "Write a Python function to reverse a string."

    result = await cascade.execute(query=query, max_tokens=60, temperature=0.5)

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 10 - Code Generation")

    logger.info("✓ Query type: Code generation")
    logger.info("✓ Test 10 PASSED")


# ==========================================
# ERROR HANDLING & EDGE CASES
# ==========================================


@pytest.mark.asyncio
async def test_no_crashes_with_logprobs(providers, anthropic_drafter, openai_verifier):
    """Test 11: Verify no crashes occur with logprobs enabled."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 11: Stability - No Crashes with Logprobs")
    logger.info("=" * 60)

    test_cases = [
        ("Short query", 20, 0.3, 5),
        ("Medium query with multiple sentences", 50, 0.7, 10),
        ("Longer detailed query requiring more tokens", 80, 0.9, 15),
    ]

    for query, max_tokens, temperature, chunk_size in test_cases:
        logger.info(f"\nTesting: max_tokens={max_tokens}, temp={temperature}, chunk={chunk_size}")

        cascade = TokenLevelSpeculativeCascade(
            drafter=anthropic_drafter,
            verifier=openai_verifier,
            providers=providers,
            chunk_size=chunk_size,
            verbose=False,
        )

        result = await cascade.execute(query=query, max_tokens=max_tokens, temperature=temperature)

        assert result is not None
        assert result.content

        # Track stats
        test_stats.add_result(result)

        logger.info(
            f"✓ Completed: {len(result.content)} chars, acceptance={result.acceptance_rate:.1%}"
        )

    logger.info("\n✓ All stability tests passed - no crashes")
    logger.info("✓ Test 11 PASSED")


@pytest.mark.asyncio
async def test_reverse_cascade(providers, openai_drafter, anthropic_verifier):
    """Test 12: Test with OpenAI as drafter, Anthropic as verifier."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 12: Reverse Cascade (OpenAI → Anthropic)")
    logger.info("=" * 60)

    cascade = TokenLevelSpeculativeCascade(
        drafter=openai_drafter,
        verifier=anthropic_verifier,
        providers=providers,
        chunk_size=10,
        verbose=True,
    )

    query = "What are the benefits of renewable energy?"

    result = await cascade.execute(query=query, max_tokens=40, temperature=0.7)

    assert result.drafter_model == openai_drafter.name
    assert result.verifier_model == anthropic_verifier.name
    assert result.acceptance_rate >= 0, "Acceptance rate should be non-negative"

    # Track stats
    test_stats.add_result(result)
    print_result_stats(result, "Test 12 - Reverse Cascade")

    logger.info("✓ Reverse cascade works!")
    logger.info("✓ Test 12 PASSED")


@pytest.mark.asyncio
async def test_cascade_stats_summary(providers, anthropic_drafter, openai_verifier):
    """Test 13: Verify cascade statistics are tracked correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 13: Cascade Statistics")
    logger.info("=" * 60)

    cascade = TokenLevelSpeculativeCascade(
        drafter=anthropic_drafter,
        verifier=openai_verifier,
        providers=providers,
        chunk_size=10,
        verbose=False,
    )

    # Run 3 queries
    queries = ["What is AI?", "Explain machine learning.", "What is deep learning?"]

    for i, query in enumerate(queries, 1):
        logger.info(f"\nQuery {i}/3: {query}")
        result = await cascade.execute(query=query, max_tokens=30, temperature=0.7)
        logger.info(f"✓ Acceptance: {result.acceptance_rate:.1%}")

        # Track stats
        test_stats.add_result(result)

    # Get stats
    stats = cascade.get_stats()

    assert stats["total_executions"] == 3
    assert stats["tokens_drafted"] >= 0
    assert stats["tokens_accepted"] >= 0
    assert stats["avg_acceptance_rate"] >= 0
    assert stats["avg_speedup"] >= 0

    logger.info("\n✓ Statistics tracking works correctly")
    logger.info("✓ Test 13 PASSED")


# ==========================================
# FINAL SUMMARY
# ==========================================


@pytest.fixture(scope="session", autouse=True)
def print_final_stats(request):
    """Print final statistics after all tests complete."""

    def finalizer():
        test_stats.print_summary()

    request.addfinalizer(finalizer)


# ==========================================
# RUN ALL TESTS
# ==========================================

if __name__ == "__main__":
    """Run all tests with detailed output."""
    import sys

    print("\n" + "=" * 70)
    print("PHASE 2.1: CASCADE INTEGRATION TESTS WITH LOGPROBS")
    print("=" * 70)
    print("\nTesting: Anthropic Haiku 3.5 + OpenAI GPT-4o Mini")
    print("Coverage: Basic execution, logprobs flow, deferral strategies")
    print("Statistics: Cost savings, speedup, acceptance rates")
    print("=" * 70 + "\n")

    # Run with pytest
    exit_code = pytest.main([__file__, "-v", "-s", "--tb=short", "--color=yes"])

    sys.exit(exit_code)
