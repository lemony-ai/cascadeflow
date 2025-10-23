"""
Direct MVP cascade testing - no agent overhead.

Tests pure cascade performance:
- Acceptance rates
- Cost savings
- Speedup
- Quality validation
- Cross-provider compatibility
"""

import os

import pytest
from cascadeflow.config import ModelConfig
from cascadeflow.speculative import WholeResponseCascade

from cascadeflow.providers import PROVIDER_REGISTRY
from cascadeflow.quality import QualityConfig


# Test configurations
@pytest.fixture
def test_models():
    """Get test model configurations."""
    models = {
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
    }
    return models


@pytest.fixture
def providers():
    """Initialize providers."""
    providers = {}

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        providers["openai"] = PROVIDER_REGISTRY["openai"]()

    # Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        providers["anthropic"] = PROVIDER_REGISTRY["anthropic"]()

    return providers


@pytest.mark.asyncio
async def test_simple_query_acceptance(test_models, providers):
    """Test that simple queries get accepted with high rate."""
    if "openai" not in providers:
        pytest.skip("OpenAI API key not available")

    drafter = test_models["openai_cheap"]
    verifier = test_models["openai_expensive"]

    # Use lenient config for simple queries
    config = QualityConfig.for_development()

    cascade = WholeResponseCascade(
        drafter=drafter, verifier=verifier, providers=providers, quality_config=config, verbose=True
    )

    # Simple query
    result = await cascade.execute(query="What is 2+2?", max_tokens=20, temperature=0.7)

    print("\n" + "=" * 60)
    print("SIMPLE QUERY TEST")
    print("=" * 60)
    print("Query: 'What is 2+2?'")
    print(f"Content: {result.content}")
    print(f"Draft accepted: {result.draft_accepted}")
    print(f"Confidence: {result.draft_confidence:.2f}")
    print(f"Cost: ${result.total_cost:.6f}")
    print(f"Latency: {result.latency_ms:.0f}ms")
    print(f"Speedup: {result.speedup:.2f}x")

    # Assertions
    assert result.content, "Should have content"
    assert result.draft_accepted, "Simple query should be accepted"
    assert result.speedup > 1.0, "Should be faster than verifier alone"
    assert result.total_cost < verifier.cost, "Should cost less than verifier"


@pytest.mark.asyncio
async def test_complex_query_rejection(test_models, providers):
    """Test that complex queries may defer to verifier."""
    if "openai" not in providers:
        pytest.skip("OpenAI API key not available")

    drafter = test_models["openai_cheap"]
    verifier = test_models["openai_expensive"]

    # Use strict config
    config = QualityConfig.strict()

    cascade = WholeResponseCascade(
        drafter=drafter, verifier=verifier, providers=providers, quality_config=config, verbose=True
    )

    # Complex query
    result = await cascade.execute(
        query="Explain the philosophical implications of Gödel's incompleteness theorems in relation to artificial intelligence",
        max_tokens=100,
        temperature=0.7,
    )

    print("\n" + "=" * 60)
    print("COMPLEX QUERY TEST")
    print("=" * 60)
    print("Query: 'Gödel's incompleteness theorems...'")
    print(f"Content preview: {result.content[:100]}...")
    print(f"Draft accepted: {result.draft_accepted}")
    print(f"Reason: {result.metadata.get('reason', 'N/A')}")
    print(f"Validation checks: {result.metadata.get('validation_checks', {})}")
    print(f"Cost: ${result.total_cost:.6f}")
    print(f"Latency: {result.latency_ms:.0f}ms")

    # Assertions
    assert result.content, "Should have content"
    # Complex query with strict config may or may not be accepted
    if not result.draft_accepted:
        print("Draft rejected - using verifier (expected for complex queries)")


@pytest.mark.asyncio
async def test_cost_savings_calculation(test_models, providers):
    """Test that cost savings are calculated correctly."""
    if "openai" not in providers:
        pytest.skip("OpenAI API key not available")

    drafter = test_models["openai_cheap"]
    verifier = test_models["openai_expensive"]

    cascade = WholeResponseCascade(
        drafter=drafter,
        verifier=verifier,
        providers=providers,
        quality_config=QualityConfig.for_production(),
        verbose=True,
    )

    result = await cascade.execute(query="List three colors", max_tokens=20, temperature=0.7)

    print("\n" + "=" * 60)
    print("COST SAVINGS TEST")
    print("=" * 60)
    print(f"Drafter cost: ${drafter.cost:.6f}")
    print(f"Verifier cost: ${verifier.cost:.6f}")
    print(f"Total cost: ${result.total_cost:.6f}")
    print(f"Cost saved: ${result.metadata.get('cost_saved', 0):.6f}")
    print(f"Draft accepted: {result.draft_accepted}")

    if result.draft_accepted:
        # Should save money
        assert result.metadata["cost_saved"] > 0, "Should have positive cost savings"
        assert result.total_cost < verifier.cost, "Should cost less than verifier"
    else:
        # May cost more (draft + verifier)
        print("Draft rejected - no cost savings")


@pytest.mark.asyncio
async def test_cross_provider_openai_to_anthropic(test_models, providers):
    """Test OpenAI drafter -> Anthropic verifier."""
    if "openai" not in providers or "anthropic" not in providers:
        pytest.skip("OpenAI and Anthropic API keys required")

    drafter = test_models["openai_cheap"]
    verifier = test_models["anthropic_expensive"]

    cascade = WholeResponseCascade(
        drafter=drafter,
        verifier=verifier,
        providers=providers,
        quality_config=QualityConfig.for_production(),
        verbose=True,
    )

    result = await cascade.execute(query="What is Python?", max_tokens=50, temperature=0.7)

    print("\n" + "=" * 60)
    print("CROSS-PROVIDER TEST: OpenAI -> Anthropic")
    print("=" * 60)
    print(f"Drafter: {drafter.name} ({drafter.provider})")
    print(f"Verifier: {verifier.name} ({verifier.provider})")
    print(f"Content: {result.content[:100]}")
    print(f"Draft accepted: {result.draft_accepted}")
    print(f"Cost: ${result.total_cost:.6f}")

    # Should work without tokenization errors
    assert result.content, "Should have content"
    assert result.latency_ms > 0, "Should have positive latency"


@pytest.mark.asyncio
async def test_cross_provider_anthropic_to_openai(test_models, providers):
    """Test Anthropic drafter -> OpenAI verifier."""
    if "openai" not in providers or "anthropic" not in providers:
        pytest.skip("OpenAI and Anthropic API keys required")

    drafter = test_models["anthropic_cheap"]
    verifier = test_models["openai_expensive"]

    cascade = WholeResponseCascade(
        drafter=drafter,
        verifier=verifier,
        providers=providers,
        quality_config=QualityConfig.for_production(),
        verbose=True,
    )

    result = await cascade.execute(query="What is JavaScript?", max_tokens=50, temperature=0.7)

    print("\n" + "=" * 60)
    print("CROSS-PROVIDER TEST: Anthropic -> OpenAI")
    print("=" * 60)
    print(f"Drafter: {drafter.name} ({drafter.provider})")
    print(f"Verifier: {verifier.name} ({verifier.provider})")
    print(f"Content: {result.content[:100]}")
    print(f"Draft accepted: {result.draft_accepted}")
    print(f"Cost: ${result.total_cost:.6f}")

    # Should work without tokenization errors
    assert result.content, "Should have content"
    assert result.latency_ms > 0, "Should have positive latency"


@pytest.mark.asyncio
async def test_multiple_queries_statistics(test_models, providers):
    """Test statistics across multiple queries."""
    if "openai" not in providers:
        pytest.skip("OpenAI API key not available")

    drafter = test_models["openai_cheap"]
    verifier = test_models["openai_expensive"]

    cascade = WholeResponseCascade(
        drafter=drafter,
        verifier=verifier,
        providers=providers,
        quality_config=QualityConfig.for_production(),
        verbose=True,
    )

    # Run multiple queries
    queries = [
        "What is 1+1?",
        "What is the capital of France?",
        "List three programming languages",
        "What is Python used for?",
        "Name a color",
    ]

    results = []
    for query in queries:
        result = await cascade.execute(query=query, max_tokens=30, temperature=0.7)
        results.append(result)

    # Get statistics
    stats = cascade.get_stats()

    print("\n" + "=" * 60)
    print("MULTIPLE QUERIES STATISTICS")
    print("=" * 60)
    print(f"Total queries: {len(queries)}")
    print(f"Drafts accepted: {stats['drafts_accepted']}")
    print(f"Drafts rejected: {stats['drafts_rejected']}")
    print(f"Acceptance rate: {stats['acceptance_rate']:.1%}")
    print(f"Avg speedup: {stats.get('avg_speedup', 0):.2f}x")
    print(f"Avg cost saved: ${stats.get('avg_cost_saved', 0):.6f}")

    # Target: 40-70% acceptance rate
    assert stats["acceptance_rate"] >= 0.3, "Acceptance rate should be at least 30%"
    assert stats["acceptance_rate"] <= 0.9, "Acceptance rate should be at most 90%"

    if stats["drafts_accepted"] > 0:
        assert stats["avg_speedup"] > 1.0, "Average speedup should be > 1.0x"


@pytest.mark.asyncio
async def test_quality_config_profiles(test_models, providers):
    """Test different quality config profiles."""
    if "openai" not in providers:
        pytest.skip("OpenAI API key not available")

    drafter = test_models["openai_cheap"]
    verifier = test_models["openai_expensive"]
    query = "What is machine learning?"

    configs = {
        "development": QualityConfig.for_development(),
        "production": QualityConfig.for_production(),
        "strict": QualityConfig.strict(),
    }

    print("\n" + "=" * 60)
    print("QUALITY CONFIG PROFILES TEST")
    print("=" * 60)

    for name, config in configs.items():
        cascade = WholeResponseCascade(
            drafter=drafter,
            verifier=verifier,
            providers=providers,
            quality_config=config,
            verbose=False,
        )

        result = await cascade.execute(query=query, max_tokens=50, temperature=0.7)

        print(f"\n{name.upper()} config:")
        print(f"  Threshold: {config.confidence_threshold}")
        print(f"  Draft accepted: {result.draft_accepted}")
        print(f"  Confidence: {result.draft_confidence:.2f}")

        assert result.content, f"{name} config should produce content"


@pytest.mark.asyncio
async def test_confidence_threshold_override(test_models, providers):
    """Test manual confidence threshold override."""
    if "openai" not in providers:
        pytest.skip("OpenAI API key not available")

    drafter = test_models["openai_cheap"]
    verifier = test_models["openai_expensive"]

    # Start with low threshold
    cascade = WholeResponseCascade(
        drafter=drafter,
        verifier=verifier,
        providers=providers,
        confidence_threshold=0.50,  # Low threshold
        verbose=True,
    )

    result1 = await cascade.execute(query="What is Python?", max_tokens=30, temperature=0.7)

    # Update to high threshold
    cascade.confidence_threshold = 0.90  # High threshold

    result2 = await cascade.execute(query="What is Python?", max_tokens=30, temperature=0.7)

    print("\n" + "=" * 60)
    print("THRESHOLD OVERRIDE TEST")
    print("=" * 60)
    print("Low threshold (0.50):")
    print(f"  Draft accepted: {result1.draft_accepted}")
    print(f"  Confidence: {result1.draft_confidence:.2f}")
    print("\nHigh threshold (0.90):")
    print(f"  Draft accepted: {result2.draft_accepted}")
    print(f"  Confidence: {result2.draft_confidence:.2f}")

    # With same query, high threshold should be more selective
    # (though not guaranteed to differ with small sample)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
