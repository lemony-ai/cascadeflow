"""Tests for CascadeAgent."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from cascadeflow import CascadeAgent, ModelConfig, UserTier
from cascadeflow.result import CascadeResult
from cascadeflow.providers.base import ModelResponse
from cascadeflow.exceptions import BudgetExceededError, QualityThresholdError


@pytest.fixture
def basic_models():
    """Basic model configuration for testing."""
    return [
        ModelConfig(name="test-cheap", provider="openai", cost=0.001),
        ModelConfig(name="test-expensive", provider="openai", cost=0.01),
    ]


@pytest.fixture
def mock_providers():
    """Mock providers for testing."""
    with patch("cascadeflow.agent.PROVIDER_REGISTRY") as registry:
        mock_provider = MagicMock()
        registry.__getitem__.return_value = lambda: mock_provider
        yield mock_provider


class TestCascadeAgent:
    """Tests for CascadeAgent."""

    def test_init_basic(self, basic_models):
        """Test basic initialization."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            agent = CascadeAgent(basic_models)
            assert len(agent.models) == 2
            assert agent.config is not None

    def test_init_with_tiers(self, basic_models):
        """Test initialization with user tiers."""
        tiers = {
            "free": UserTier(name="free", max_budget=0.001),
            "pro": UserTier(name="pro", max_budget=0.01),
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            agent = CascadeAgent(basic_models, tiers=tiers)
            assert len(agent.tiers) == 2
            assert "free" in agent.tiers

    @pytest.mark.asyncio
    async def test_run_success_first_model(self, basic_models):
        """Test successful run with first model."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            agent = CascadeAgent(basic_models)

            # Mock provider response
            mock_response = ModelResponse(
                content="Test response",
                model="test-cheap",
                provider="openai",
                cost=0.001,
                tokens_used=50,
                confidence=0.9,
                latency_ms=100,
                metadata={}
            )

            with patch.object(
                    agent.providers["openai"],
                    "complete",
                    return_value=mock_response
            ):
                result = await agent.run("Test query")

                assert isinstance(result, CascadeResult)
                assert result.model_used == "test-cheap"
                assert result.total_cost == 0.001
                assert result.cascaded == False
                assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_run_cascade_to_second_model(self, basic_models):
        """Test cascading to second model."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            agent = CascadeAgent(basic_models)

            # First model: low confidence
            mock_response_1 = ModelResponse(
                content="Weak response",
                model="test-cheap",
                provider="openai",
                cost=0.001,
                tokens_used=20,
                confidence=0.5,  # Below threshold
                latency_ms=50,
                metadata={}
            )

            # Second model: high confidence
            mock_response_2 = ModelResponse(
                content="Strong response",
                model="test-expensive",
                provider="openai",
                cost=0.01,
                tokens_used=100,
                confidence=0.9,  # Above threshold
                latency_ms=200,
                metadata={}
            )

            with patch.object(
                    agent.providers["openai"],
                    "complete",
                    side_effect=[mock_response_1, mock_response_2]
            ):
                result = await agent.run("Test query")

                assert result.model_used == "test-expensive"
                assert result.total_cost == 0.011  # Both models
                assert result.cascaded == True
                assert result.attempts == 2
                assert len(result.cascade_path) == 2

    @pytest.mark.asyncio
    async def test_run_budget_exceeded(self, basic_models):
        """Test budget exceeded error."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            agent = CascadeAgent(basic_models)

            mock_response = ModelResponse(
                content="Test",
                model="test-cheap",
                provider="openai",
                cost=0.001,
                tokens_used=50,
                confidence=0.5,  # Low, will try to cascade
                latency_ms=100,
                metadata={}
            )

            with patch.object(
                    agent.providers["openai"],
                    "complete",
                    return_value=mock_response
            ):
                with pytest.raises(BudgetExceededError):
                    await agent.run("Test query", max_budget=0.001)  # Only enough for first

    @pytest.mark.asyncio
    async def test_run_with_user_tier(self, basic_models):
        """Test run with user tier applied."""
        tiers = {
            "free": UserTier(name="free", max_budget=0.001, quality_threshold=0.6)
        }

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            agent = CascadeAgent(basic_models, tiers=tiers)

            mock_response = ModelResponse(
                content="Test response",
                model="test-cheap",
                provider="openai",
                cost=0.001,
                tokens_used=50,
                confidence=0.7,  # Above tier threshold
                latency_ms=100,
                metadata={}
            )

            with patch.object(
                    agent.providers["openai"],
                    "complete",
                    return_value=mock_response
            ):
                result = await agent.run("Test query", user_tier="free")

                assert result.user_tier == "free"
                assert result.total_cost <= 0.001

    def test_get_stats(self, basic_models):
        """Test statistics tracking."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            agent = CascadeAgent(basic_models)
            stats = agent.get_stats()

            assert "total_queries" in stats
            assert "total_cost" in stats
            assert "avg_cost" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])