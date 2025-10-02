"""Tests for OpenAI provider."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from cascadeflow.providers.openai import OpenAIProvider
from cascadeflow.providers.base import ModelResponse
from cascadeflow.exceptions import ProviderError, ModelError


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
        "choices": [
            {
                "message": {"content": "This is a test response."},
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
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
            result = await openai_provider.complete(
                prompt="Test prompt",
                model="gpt-3.5-turbo"
            )

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

            result = await openai_provider.complete(
                prompt="Test",
                model="gpt-4",
                system_prompt="You are a helpful assistant."
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
                "Unauthorized",
                request=MagicMock(),
                response=mock_response
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
                "Too Many Requests",
                request=MagicMock(),
                response=mock_response
            )

            with pytest.raises(ProviderError, match="rate limit"):
                await openai_provider.complete("Test", "gpt-3.5-turbo")

    def test_estimate_cost_gpt35(self, openai_provider):
        """Test cost estimation for GPT-3.5."""
        cost = openai_provider.estimate_cost(1000, "gpt-3.5-turbo")
        assert cost == 0.002  # $0.002 per 1K tokens

    def test_estimate_cost_gpt4(self, openai_provider):
        """Test cost estimation for GPT-4."""
        cost = openai_provider.estimate_cost(1000, "gpt-4")
        assert cost == 0.03  # $0.03 per 1K tokens

    def test_estimate_cost_unknown_model(self, openai_provider):
        """Test cost estimation for unknown model."""
        cost = openai_provider.estimate_cost(1000, "unknown-model")
        assert cost == 0.03  # Defaults to GPT-4 pricing

    def test_calculate_confidence_stop(self, openai_provider):
        """Test confidence calculation with stop finish_reason."""
        metadata = {
            "finish_reason": "stop"
        }
        confidence = openai_provider.calculate_confidence(
            "This is a complete response.",
            metadata
        )
        assert confidence > 0.7

    def test_calculate_confidence_length(self, openai_provider):
        """Test confidence calculation with length finish_reason."""
        metadata = {
            "finish_reason": "length"
        }
        confidence = openai_provider.calculate_confidence(
            "This is an incomplete",
            metadata
        )
        assert confidence < 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])