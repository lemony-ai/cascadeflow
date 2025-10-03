"""Integration tests for full CascadeAgent with Day 4.2 features."""

import pytest
import asyncio
import os
from cascadeflow.agent import CascadeAgent
from cascadeflow.config import ModelConfig, DEFAULT_TIERS
from cascadeflow.complexity import QueryComplexity


@pytest.fixture
def test_models():
    """Create test models."""
    return [
        ModelConfig(
            name="test-small",
            provider="ollama",
            cost=0.0,
            speed_ms=300,
            quality_score=0.6,
            domains=["general"]
        ),
        ModelConfig(
            name="test-code",
            provider="ollama",
            cost=0.0,
            speed_ms=400,
            quality_score=0.7,
            domains=["code"],
            keywords=["python", "javascript", "code"]
        ),
        ModelConfig(
            name="test-large",
            provider="ollama",
            cost=0.01,
            speed_ms=1000,
            quality_score=0.9,
            domains=["general"]
        ),
    ]


class TestAgentInitialization:

    def test_init_with_semantic_routing(self, test_models):
        """Test agent initialization with semantic routing."""
        agent = CascadeAgent(
            models=test_models,
            routing_strategy="semantic",
            verbose=True
        )

        assert agent.routing_strategy in ["semantic", "keyword"]
        assert agent.complexity_detector is not None
        assert agent.execution_planner is not None
        print(f"\n✓ Agent initialized with routing: {agent.routing_strategy}")

    def test_init_with_keyword_routing(self, test_models):
        """Test agent initialization with keyword-only routing."""
        agent = CascadeAgent(
            models=test_models,
            routing_strategy="keyword",
            verbose=True
        )

        assert agent.routing_strategy == "keyword"
        assert agent.semantic_router is None
        print("\n✓ Agent initialized with keyword routing")

    def test_semantic_router_precomputation(self, test_models):
        """Test that embeddings are precomputed if available."""
        agent = CascadeAgent(
            models=test_models,
            routing_strategy="semantic",
            verbose=True
        )

        if agent.semantic_router and agent.semantic_router.is_available():
            assert len(agent.semantic_router.model_embeddings) == len(test_models)
            print(f"\n✓ Precomputed embeddings for {len(test_models)} models")
        else:
            print("\n⚠️ Semantic routing unavailable, using keyword routing")


class TestAgentRouting:

    @pytest.mark.asyncio
    async def test_complexity_detection(self, test_models):
        """Test that agent detects complexity correctly."""
        agent = CascadeAgent(
            models=test_models,
            verbose=True
        )

        plan_captured = None

        async def mock_execute(*args, **kwargs):
            nonlocal plan_captured
            plan_captured = kwargs.get('plan')
            from cascadeflow.result import CascadeResult
            return CascadeResult(
                content="test",
                model_used="test-small",
                provider="ollama",
                total_cost=0.0,
                total_tokens=10,
                confidence=0.9,
                latency_ms=100,
                strategy="direct"
            )

        agent._execute_plan = mock_execute

        await agent.run("What is 2+2?")
        assert plan_captured is not None
        print(f"\nTrivial query strategy: {plan_captured.strategy.value}")
        print(f"Reasoning: {plan_captured.reasoning}")

    @pytest.mark.asyncio
    async def test_domain_routing(self, test_models):
        """Test that code queries route to code models."""
        agent = CascadeAgent(
            models=test_models,
            verbose=True
        )

        plan_captured = None

        async def mock_execute(*args, **kwargs):
            nonlocal plan_captured
            plan_captured = kwargs.get('plan')
            from cascadeflow.result import CascadeResult
            return CascadeResult(
                content="test",
                model_used="test-code",
                provider="ollama",
                total_cost=0.0,
                total_tokens=10,
                confidence=0.9,
                latency_ms=100,
                strategy="direct"
            )

        agent._execute_plan = mock_execute

        await agent.run("Fix this Python bug")

        # Check that code domain was detected
        assert "code" in plan_captured.metadata["query_domains"]

        # Check that domain boost was applied
        top_models = plan_captured.metadata["top_3_models"]
        print(f"\nTop models for code query:")
        for model in top_models:
            print(f"  {model['name']}: boost={model['domain_boost']:.1f}x")

        # Code model should have domain boost
        code_model = next((m for m in top_models if m['name'] == 'test-code'), None)
        assert code_model is not None
        assert code_model['domain_boost'] == 2.0


class TestAgentFeatures:

    @pytest.mark.asyncio
    async def test_caching(self, test_models):
        """Test response caching."""
        agent = CascadeAgent(
            models=test_models,
            enable_caching=True,
            verbose=True
        )

        # Mock provider
        async def mock_complete(model, prompt, **kwargs):
            return {"content": "cached response", "tokens_used": 10}

        for provider in agent.providers.values():
            provider.complete = mock_complete

        query = "What is Python?"

        # First call - should execute
        result1 = await agent.run(query, enable_caching=True)

        # Second call - should hit cache
        result2 = await agent.run(query, enable_caching=True)

        assert result1.content == result2.content

        cache_stats = agent.cache.get_stats()
        print(f"\nCache stats: hits={cache_stats['hits']}, misses={cache_stats['misses']}")
        assert cache_stats['hits'] >= 1

    @pytest.mark.asyncio
    async def test_user_tiers(self, test_models):
        """Test user tier application."""
        agent = CascadeAgent(
            models=test_models,
            tiers=DEFAULT_TIERS,
            verbose=True
        )

        plan_captured = None

        async def mock_execute(*args, **kwargs):
            nonlocal plan_captured
            plan_captured = kwargs.get('plan')
            from cascadeflow.result import CascadeResult
            return CascadeResult(
                content="test",
                model_used="test-small",
                provider="ollama",
                total_cost=0.0,
                total_tokens=10,
                confidence=0.9,
                latency_ms=100,
                strategy="direct"
            )

        agent._execute_plan = mock_execute

        # Test with free tier (cost priority)
        await agent.run("Simple query", user_tier="free")
        free_optimization = plan_captured.metadata["optimization"]
        assert free_optimization["cost"] == 0.70

        # Test with enterprise tier (speed priority)
        await agent.run("Simple query", user_tier="enterprise")
        enterprise_optimization = plan_captured.metadata["optimization"]
        assert enterprise_optimization["speed"] == 0.60

        print(f"\nFree tier optimization: {free_optimization}")
        print(f"Enterprise tier optimization: {enterprise_optimization}")


class TestAgentStats:

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, test_models):
        """Test that agent tracks statistics."""
        agent = CascadeAgent(
            models=test_models,
            verbose=True
        )

        # Mock provider
        async def mock_complete(model, prompt, **kwargs):
            return {"content": "response", "tokens_used": 10}

        for provider in agent.providers.values():
            provider.complete = mock_complete

        # Run some queries
        await agent.run("Query 1")
        await agent.run("Query 2")
        await agent.run("Query 3")

        stats = agent.get_stats()

        assert stats["total_queries"] == 3
        assert "model_usage" in stats
        assert "complexity" in stats

        print(f"\nAgent stats after 3 queries:")
        print(f"  Total cost: ${stats['total_cost']:.6f}")
        print(f"  Avg cost: ${stats['avg_cost']:.6f}")
        print(f"  Model usage: {stats['model_usage']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])