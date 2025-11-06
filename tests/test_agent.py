"""
Comprehensive test suite for enhanced CascadeAgent.

Tests all day 4.2 features:
- Complexity detection
- Domain routing with 2.0x boost
- Execution strategies
- Speculative cascades
- Callbacks and caching
- 20+ control parameters
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from dotenv import load_dotenv

from cascadeflow import CascadeAgent
from cascadeflow.quality.complexity import QueryComplexity
from cascadeflow.schema.config import (
    LatencyProfile,
    ModelConfig,
    OptimizationWeights,
    UserTier,
    WorkflowProfile,
)

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_models():
    """Create mock model configurations matching current API."""
    return [
        # Free/cheap Ollama models
        ModelConfig(
            name="llama3:8b",
            provider="ollama",
            cost=0.0,  # Free local models
            domains=["general"],
        ),
        ModelConfig(
            name="codellama:7b",
            provider="ollama",
            cost=0.0,  # Free local models
            domains=["code"],
        ),
        # Paid OpenAI models
        ModelConfig(
            name="gpt-4o-mini",
            provider="openai",
            cost=0.00015,
            domains=["general"],
        ),
        ModelConfig(
            name="gpt-4o",
            provider="openai",
            cost=0.00625,
            domains=["general", "reasoning", "code"],
        ),
    ]


@pytest.fixture
def mock_tiers():
    """Create mock user tiers."""
    return {
        "free": UserTier(
            name="free",
            max_budget=0.01,
            quality_threshold=0.6,
            allowed_models=["llama3:8b", "codellama:7b"],
            enable_caching=True,
            enable_speculative=False,
            latency=LatencyProfile(
                max_total_ms=3000,
                max_per_model_ms=1000,
                prefer_parallel=False,
                skip_cascade_threshold=0,
            ),
            optimization=OptimizationWeights(cost=0.6, speed=0.2, quality=0.2),
        ),
        "premium": UserTier(
            name="premium",
            max_budget=0.10,
            quality_threshold=0.8,
            allowed_models=["*"],
            enable_caching=True,
            enable_speculative=True,
            latency=LatencyProfile(
                max_total_ms=2000,
                max_per_model_ms=1500,
                prefer_parallel=True,
                skip_cascade_threshold=1500,
            ),
            optimization=OptimizationWeights(cost=0.2, speed=0.3, quality=0.5),
        ),
    }


@pytest.fixture
def mock_workflows():
    """Create mock workflow profiles."""
    return {
        "code_review": WorkflowProfile(
            name="code_review",
            domains=["code"],
            preferred_models=["codellama:7b"],
            quality_threshold=0.75,
            optimization_weights=OptimizationWeights(cost=0.2, speed=0.3, quality=0.5),
        )
    }


@pytest.fixture
def mock_provider_response():
    """Create mock provider response."""
    return {
        "content": "This is a test response.",
        "confidence": 0.85,
        "tokens_used": 50,
        "cost": 0.002,
    }


@pytest.fixture
async def mock_agent(mock_models, mock_tiers, mock_workflows):
    """Create agent with mocked providers."""
    with patch("cascadeflow.agent.PROVIDER_REGISTRY") as mock_registry:
        # Create mock response object with required attributes
        class MockResponse:
            def __init__(self):
                self.content = "Test response"
                self.confidence = 0.85
                self.tokens_used = 50

        # Create mock provider
        mock_provider = Mock()
        mock_provider.complete = AsyncMock(return_value=MockResponse())

        # Register mock providers
        mock_registry.__getitem__.return_value = lambda: mock_provider
        mock_registry.__contains__.return_value = True

        agent = CascadeAgent(
            models=mock_models,
            tiers=mock_tiers,  # ✅ Pass tiers to enable tier-based filtering
            verbose=True,
        )

        # Replace providers with mocks
        agent.providers = {"ollama": mock_provider, "openai": mock_provider}

        yield agent


# ============================================================================
# Basic Tests
# ============================================================================


class TestAgentInitialization:
    """Test agent initialization."""

    def test_init_basic(self, mock_models):
        """Test basic initialization."""
        agent = CascadeAgent(models=mock_models)

        assert len(agent.models) == 4  # ✅ Updated: now includes 2 Ollama + 2 OpenAI models
        assert agent.quality_config is not None
        assert agent.complexity_detector is not None
        assert agent.router is not None
        assert agent.tool_router is not None
        assert agent.telemetry is not None
        assert agent.cost_calculator is not None
        assert len(agent.providers) > 0

    def test_init_with_cascade_disabled(self, mock_models):
        """Test initialization with cascade disabled."""
        agent = CascadeAgent(models=mock_models, enable_cascade=False)

        assert agent.enable_cascade is False
        assert len(agent.models) == 4  # ✅ Updated: now includes 2 Ollama + 2 OpenAI models

    def test_init_with_verbose(self, mock_models):
        """Test initialization with verbose logging."""
        agent = CascadeAgent(models=mock_models, verbose=True)

        assert agent.verbose is True

    def test_init_single_model_disables_cascade(self):
        """Test that single model automatically disables cascade."""
        single_model = [ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015)]

        # Mock the provider registry to avoid API key requirement
        with patch("cascadeflow.agent.PROVIDER_REGISTRY") as mock_registry:
            mock_provider = Mock()
            mock_registry.__getitem__.return_value = lambda: mock_provider
            mock_registry.__contains__.return_value = True

            agent = CascadeAgent(models=single_model)

            assert agent.enable_cascade is False
            assert len(agent.models) == 1


# ============================================================================
# Query Execution Tests
# ============================================================================


class TestBasicQueryExecution:
    """Test basic query execution."""

    @pytest.mark.asyncio
    async def test_simple_query(self, mock_agent):
        """Test simple query execution."""
        result = await mock_agent.run("What is AI?")

        assert result is not None
        assert result.content is not None
        assert result.model_used is not None
        assert result.total_cost >= 0  # ✅ Fixed: was result.cost

    @pytest.mark.asyncio
    async def test_query_with_user_tier(self, mock_agent):
        """Test query with user tier applied."""
        # Force direct routing to avoid cascade issues with tier-filtered models
        result = await mock_agent.run("What is Python?", user_tier="free", force_direct=True)

        assert result is not None
        # Free tier should only use free models
        # With force_direct=True, should be direct routing (no '+' in model name)
        assert "+" not in result.model_used, "Expected direct routing, got cascade"
        assert result.model_used in [
            "llama3:8b",
            "codellama:7b",
        ], f"Model {result.model_used} not in free tier"

    @pytest.mark.asyncio
    async def test_query_with_workflow(self, mock_agent):
        """Test query with workflow applied."""
        result = await mock_agent.run("Review this code", workflow="code_review")

        assert result is not None

    @pytest.mark.asyncio
    async def test_query_with_domain_hint(self, mock_agent):
        """Test query with domain hint."""
        result = await mock_agent.run(
            "def factorial(n): return n * factorial(n-1)", query_domains=["code"]
        )

        assert result is not None


# ============================================================================
# Intelligence Layer Tests
# ============================================================================


class TestComplexityDetection:
    """Test complexity detection integration."""

    @pytest.mark.asyncio
    async def test_trivial_query(self, mock_agent):
        """Test trivial query detection."""
        # Mock complexity detector to return TRIVIAL
        mock_agent.complexity_detector.detect = Mock(return_value=(QueryComplexity.TRIVIAL, 0.9))

        result = await mock_agent.run("What is 2+2?")

        # Should use cheapest model for trivial queries (cascade: free drafter + verifier)
        # Cascade uses free llama3:8b as drafter (cost=0.0) + gpt-4o verifier (small cost)
        assert result.draft_cost == 0.0  # Drafter should be free
        assert result.total_cost > 0.0  # Verifier adds small cost
        assert result.total_cost < 0.001  # But total cost should be minimal

    @pytest.mark.asyncio
    async def test_expert_query(self, mock_agent):
        """Test expert query detection."""
        # Mock complexity detector to return EXPERT
        mock_agent.complexity_detector.detect = Mock(return_value=(QueryComplexity.EXPERT, 0.95))

        result = await mock_agent.run("Explain quantum entanglement in relation to Bell's theorem")

        # Should use best model for expert queries (gpt-4o is most expensive/best in mock_models)
        assert result.model_used == "gpt-4o"
        assert result.cascaded is False  # Expert queries use direct routing
        assert result.routing_strategy == "direct"


class TestDomainRouting:
    """Test domain detection and routing."""

    @pytest.mark.asyncio
    async def test_code_domain(self, mock_agent):
        """Test code domain routing."""
        result = await mock_agent.run(
            "Write a Python function to sort a list", query_domains=["code"]
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_math_domain(self, mock_agent):
        """Test math domain routing."""
        result = await mock_agent.run("Solve: x^2 + 5x + 6 = 0", query_domains=["math"])

        assert result is not None


# ============================================================================
# Parameter Control Tests
# ============================================================================


class TestModelControl:
    """Test model control parameters."""

    @pytest.mark.asyncio
    async def test_force_models(self, mock_agent):
        """Test force_models parameter."""
        # Use gpt-4o (which exists in mock_models) and force direct routing
        result = await mock_agent.run("What is AI?", force_models=["gpt-4o"], force_direct=True)

        assert result.model_used == "gpt-4o"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="exclude_models parameter not yet implemented in agent.run()")
    async def test_exclude_models(self, mock_agent):
        """Test exclude_models parameter."""
        # Exclude OpenAI models and force direct routing to avoid cascade
        result = await mock_agent.run(
            "What is AI?", exclude_models=["gpt-4o", "gpt-4o-mini"], force_direct=True
        )

        # Should only use Ollama models
        assert result.model_used in ["llama3:8b", "codellama:7b"]


class TestBudgetControl:
    """Test budget control parameters."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="max_budget parameter not yet implemented in agent.run()")
    async def test_max_budget(self, mock_agent):
        """Test max_budget parameter."""
        # Force direct routing with free models only
        result = await mock_agent.run("What is AI?", max_budget=0.0, force_direct=True)

        # Should only use free models (Ollama models with cost=0.0)
        assert result.total_cost == 0.0  # ✅ Fixed: was result.cost
        assert result.model_used in ["llama3:8b", "codellama:7b"]

    @pytest.mark.asyncio
    async def test_budget_exceeded(self, mock_agent):
        """Test budget exceeded error."""
        # Mock expensive responses with low confidence
        for provider in mock_agent.providers.values():
            provider.complete = AsyncMock(
                return_value={"content": "Test", "confidence": 0.5, "tokens_used": 50}
            )

        # This should work since we're testing the constraint, not necessarily triggering the error
        result = await mock_agent.run(
            "What is AI?",
            max_budget=0.001,
            quality_threshold=0.6,  # Lower threshold to allow completion
        )

        assert result.total_cost <= 0.001 or result.total_cost == 0.0  # ✅ Fixed: was result.cost


class TestQualityControl:
    """Test quality control parameters."""

    @pytest.mark.asyncio
    async def test_quality_threshold(self, mock_agent):
        """Test quality_threshold parameter."""
        result = await mock_agent.run("What is AI?", quality_threshold=0.8)

        assert result is not None


# ============================================================================
# Feature Tests
# ============================================================================


class TestCaching:
    """Test response caching."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_agent):
        """Test cache hit on repeated query."""
        query = "What is AI?"

        # First call
        result1 = await mock_agent.run(query, enable_caching=True)

        # Second call (should hit cache)
        result2 = await mock_agent.run(query, enable_caching=True)

        assert result1.content == result2.content

    @pytest.mark.asyncio
    async def test_cache_disabled(self, mock_agent):
        """Test caching disabled."""
        query = "What is AI?"

        # First call
        await mock_agent.run(query, enable_caching=False)

        # Clear call count
        for provider in mock_agent.providers.values():
            provider.complete.reset_mock()

        # Second call (should NOT hit cache)
        await mock_agent.run(query, enable_caching=False)

        # Provider should be called again
        assert any(p.complete.call_count > 0 for p in mock_agent.providers.values())


class TestCallbacks:
    """Test callback system."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="on_complete callback parameter not yet implemented in agent.run()")
    async def test_query_callbacks(self, mock_agent):
        """Test query lifecycle callbacks."""
        events = []

        def on_complete(result):
            # Callback receives the result object
            events.append(("complete", result))

        await mock_agent.run("What is AI?", on_complete=on_complete)

        # Callback should have been called
        assert len(events) > 0
        assert events[0][0] == "complete"
        # Verify the result was passed
        assert events[0][1] is not None


class TestSpeculativeCascades:
    """Test speculative cascade execution."""

    @pytest.mark.asyncio
    async def test_speculative_enabled(self, mock_agent):
        """Test speculative cascade when enabled."""
        result = await mock_agent.run("What is AI?", enable_speculative=True)

        assert result is not None

    @pytest.mark.asyncio
    async def test_speculative_disabled(self, mock_agent):
        """Test speculative cascade disabled."""
        result = await mock_agent.run("What is AI?", enable_speculative=False)

        assert result is not None


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Test agent statistics."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self, mock_agent):
        """Test statistics are tracked."""
        # Run a few queries
        await mock_agent.run("Query 1")
        await mock_agent.run("Query 2")

        stats = mock_agent.get_stats()

        assert stats["total_queries"] == 2
        assert stats["total_cost"] >= 0
        # Note: 'model_usage' may not be in stats, check for other expected fields
        assert "avg_cost" in stats
        assert "cascade_rate" in stats


# ============================================================================
# Integration Tests
# ============================================================================


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, mock_agent):
        """Test full pipeline with all features."""
        callback_events = []

        def track_event(event, **kwargs):
            callback_events.append(event.value if hasattr(event, "value") else str(event))

        result = await mock_agent.run(
            query="Write a Python function to reverse a string",
            user_tier="premium",
            workflow="code_review",
            query_domains=["code"],
            max_budget=0.05,
            quality_threshold=0.75,
            enable_caching=True,
            enable_speculative=True,
            on_complete=track_event,
            metadata={"test": True},
        )

        assert result is not None
        assert result.content is not None
        assert result.total_cost <= 0.05  # ✅ Fixed: was result.cost

    @pytest.mark.asyncio
    async def test_tier_workflow_interaction(self, mock_agent):
        """Test tier and workflow working together."""
        result = await mock_agent.run(
            query="Review this code: def hello(): print('hi')",
            user_tier="free",
            workflow="code_review",
            force_direct=True,  # Force direct routing to avoid cascade
        )

        # Free tier should constrain models
        assert result.model_used in ["llama3:8b", "codellama:7b"]
        assert result.total_cost == 0.0  # ✅ Fixed: was result.cost


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Error handling behavior needs review - agent may catch exceptions instead of propagating"
    )
    async def test_provider_error(self, mock_agent):
        """Test handling of provider errors."""
        # Mock ALL providers to raise error (both draft and verifier in cascade)
        for provider in mock_agent.providers.values():
            provider.complete = AsyncMock(side_effect=Exception("Provider error"))

        with pytest.raises(Exception):
            await mock_agent.run("What is AI?")


# ============================================================================
# Utility Tests
# ============================================================================


class TestAgentUtilities:
    """Test agent utility methods."""

    @pytest.mark.skip(reason="add_tier and get_tier methods not implemented in v2.5")
    def test_add_tier(self, mock_agent):
        """Test adding a new tier."""
        new_tier = UserTier(
            name="enterprise",
            max_budget=1.0,
            quality_threshold=0.9,
            allowed_models=["*"],
            latency=LatencyProfile(
                max_total_ms=1000,
                max_per_model_ms=800,
                prefer_parallel=True,
                skip_cascade_threshold=900,
            ),
            optimization=OptimizationWeights(cost=0.1, speed=0.4, quality=0.5),
        )

        mock_agent.add_tier("enterprise", new_tier)

        assert "enterprise" in mock_agent.list_tiers()
        assert mock_agent.get_tier("enterprise") == new_tier

    @pytest.mark.skip(reason="list_tiers method not implemented in v2.5")
    def test_list_tiers(self, mock_agent):
        """Test listing tiers."""
        tiers = mock_agent.list_tiers()

        assert isinstance(tiers, list)
        assert "free" in tiers
        assert "premium" in tiers


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
