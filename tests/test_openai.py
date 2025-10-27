"""Tests for OpenAI provider."""

import os
from unittest.mock import MagicMock, patch

import pytest
from cascadeflow.exceptions import ProviderError

from cascadeflow.providers.base import ModelResponse
from cascadeflow.providers.openai import OpenAIProvider


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-12345"}):
        yield


@pytest.fixture
def openai_provider(mock_env):
    """Create OpenAI provider for testing."""
    return OpenAIProvider()


@pytest.fixture
def mock_openai_response():
    """Mock successful OpenAI API response."""
    return {
        "choices": [{"message": {"content": "This is a test response."}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        provider = OpenAIProvider(api_key="sk-explicit-key")
        assert provider.api_key == "sk-explicit-key"

    def test_init_from_env(self, mock_env):
        """Test initialization from environment variable."""
        provider = OpenAIProvider()
        assert provider.api_key == "sk-test-key-12345"

    def test_init_no_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OpenAI API key not found"):
                OpenAIProvider()

    @pytest.mark.asyncio
    async def test_complete_success(self, openai_provider, mock_openai_response):
        """Test successful completion."""
        with patch.object(openai_provider.client, "post") as mock_post:
            # Mock HTTP response
            mock_response = MagicMock()
            mock_response.json.return_value = mock_openai_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            # Call complete
            result = await openai_provider.complete(prompt="Test prompt", model="gpt-3.5-turbo")

            # Verify result
            assert isinstance(result, ModelResponse)
            assert result.content == "This is a test response."
            assert result.model == "gpt-3.5-turbo"
            assert result.provider == "openai"
            assert result.tokens_used == 30
            assert 0 <= result.confidence <= 1

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, openai_provider, mock_openai_response):
        """Test completion with system prompt."""
        with patch.object(openai_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_openai_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await openai_provider.complete(
                prompt="Test", model="gpt-4", system_prompt="You are a helpful assistant."
            )

            # Verify system prompt was included
            call_args = mock_post.call_args
            messages = call_args[1]["json"]["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_complete_http_error(self, openai_provider):
        """Test handling of HTTP errors."""
        with patch.object(openai_provider.client, "post") as mock_post:
            import httpx

            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_post.side_effect = httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response
            )

            with pytest.raises(ProviderError, match="Invalid OpenAI API key"):
                await openai_provider.complete("Test", "gpt-3.5-turbo")

    @pytest.mark.asyncio
    async def test_complete_rate_limit(self, openai_provider):
        """Test handling of rate limit errors."""
        with patch.object(openai_provider.client, "post") as mock_post:
            import httpx

            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_post.side_effect = httpx.HTTPStatusError(
                "Too Many Requests", request=MagicMock(), response=mock_response
            )

            with pytest.raises(ProviderError, match="rate limit"):
                await openai_provider.complete("Test", "gpt-3.5-turbo")

    def test_estimate_cost_gpt35_accurate(self, openai_provider):
        """Test accurate cost estimation for GPT-3.5 with input/output split."""
        # 10 input tokens, 20 output tokens
        cost = openai_provider.estimate_cost(
            tokens=30, model="gpt-3.5-turbo", prompt_tokens=10, completion_tokens=20
        )
        # Expected: (10/1000 * 0.0005) + (20/1000 * 0.0015) = 0.000005 + 0.00003 = 0.000035
        assert abs(cost - 0.000035) < 0.0000001

    def test_estimate_cost_gpt4_accurate(self, openai_provider):
        """Test accurate cost estimation for GPT-4 with input/output split."""
        # 100 input tokens, 200 output tokens
        cost = openai_provider.estimate_cost(
            tokens=300, model="gpt-4", prompt_tokens=100, completion_tokens=200
        )
        # Expected: (100/1000 * 0.030) + (200/1000 * 0.060) = 0.003 + 0.012 = 0.015
        assert abs(cost - 0.015) < 0.0000001

    def test_estimate_cost_gpt4o_mini(self, openai_provider):
        """Test cost estimation for GPT-4o-mini."""
        cost = openai_provider.estimate_cost(
            tokens=1000, model="gpt-4o-mini", prompt_tokens=500, completion_tokens=500
        )
        # Pricing may vary - verify it's reasonable for GPT-4o-mini
        assert cost > 0  # Has actual cost
        assert cost < 0.01  # Should be relatively cheap for this model

    def test_estimate_cost_fallback(self, openai_provider):
        """Test cost estimation fallback without split."""
        cost = openai_provider.estimate_cost(1000, "gpt-3.5-turbo")
        # Should use blended rate: 0.3 * 0.0005 + 0.7 * 0.0015 = 0.00015 + 0.00105 = 0.0012
        assert abs(cost - 0.0012) < 0.0000001

    def test_estimate_cost_unknown_model(self, openai_provider):
        """Test cost estimation for unknown model defaults to GPT-4."""
        cost = openai_provider.estimate_cost(
            tokens=1000, model="unknown-model", prompt_tokens=500, completion_tokens=500
        )
        # Should default to GPT-4: (500/1000 * 0.030) + (500/1000 * 0.060) = 0.045
        assert abs(cost - 0.045) < 0.0000001

    def test_calculate_confidence_stop(self, openai_provider):
        """Test confidence calculation with stop finish_reason."""
        metadata = {"finish_reason": "stop"}
        confidence = openai_provider.calculate_confidence("This is a complete response.", metadata)
        assert confidence > 0.7

    def test_calculate_confidence_length(self, openai_provider):
        """Test confidence calculation with length finish_reason."""
        metadata = {"finish_reason": "length"}
        confidence = openai_provider.calculate_confidence("This is an incomplete", metadata)
        assert confidence < 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
