"""Tests for Groq provider."""

import os
from unittest.mock import MagicMock, patch

import pytest
from cascadeflow.exceptions import ProviderError

from cascadeflow.providers.base import ModelResponse
from cascadeflow.providers.groq import GroqProvider


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_key_12345"}):
        yield


@pytest.fixture
def groq_provider(mock_env):
    """Create Groq provider for testing."""
    return GroqProvider()


@pytest.fixture
def mock_groq_response():
    """Mock successful Groq API response."""
    return {
        "choices": [
            {"message": {"content": "This is a test response from Groq."}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


class TestGroqProvider:
    """Tests for Groq provider."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        provider = GroqProvider(api_key="gsk_explicit_key")
        assert provider.api_key == "gsk_explicit_key"

    def test_init_from_env(self, mock_env):
        """Test initialization from environment variable."""
        provider = GroqProvider()
        assert provider.api_key == "gsk_test_key_12345"

    def test_init_no_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Groq API key not found"):
                GroqProvider()

    @pytest.mark.asyncio
    async def test_complete_success(self, groq_provider, mock_groq_response):
        """Test successful completion."""
        with patch.object(groq_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_groq_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await groq_provider.complete(
                prompt="Test prompt", model="llama-3.1-8b-instant"
            )

            assert isinstance(result, ModelResponse)
            assert result.content == "This is a test response from Groq."
            assert result.model == "llama-3.1-8b-instant"
            assert result.provider == "groq"
            # Groq has very low cost (LiteLLM tracks actual pricing)
            assert result.cost < 0.0001  # Very cheap, approximately free
            assert result.tokens_used == 30
            assert 0 <= result.confidence <= 1

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, groq_provider, mock_groq_response):
        """Test completion with system prompt."""
        with patch.object(groq_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_groq_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await groq_provider.complete(
                prompt="Test",
                model="llama-3.1-70b-versatile",
                system_prompt="You are a helpful assistant.",
            )

            # Verify system prompt was included
            call_args = mock_post.call_args
            messages = call_args[1]["json"]["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_complete_http_error(self, groq_provider):
        """Test handling of HTTP errors."""
        with patch.object(groq_provider.client, "post") as mock_post:
            import httpx

            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_post.side_effect = httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response
            )

            with pytest.raises(ProviderError, match="Invalid Groq API key"):
                await groq_provider.complete("Test", "llama-3.1-8b-instant")

    @pytest.mark.asyncio
    async def test_complete_rate_limit(self, groq_provider):
        """Test handling of rate limit errors."""
        with patch.object(groq_provider.client, "post") as mock_post:
            import httpx

            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_post.side_effect = httpx.HTTPStatusError(
                "Too Many Requests", request=MagicMock(), response=mock_response
            )

            with pytest.raises(ProviderError, match="rate limit"):
                await groq_provider.complete("Test", "llama-3.1-8b-instant")

    def test_estimate_cost_llama_8b(self, groq_provider):
        """Test cost estimation for Llama 3.1 8B."""
        cost = groq_provider.estimate_cost(1000, "llama-3.1-8b-instant")
        # Groq has low cost (accurate pricing as of Oct 2025)
        assert cost > 0  # Has actual cost
        assert cost < 0.001  # But very cheap (< $0.001 per 1K tokens)

    def test_estimate_cost_llama_70b(self, groq_provider):
        """Test cost estimation for Llama 3.1 70B."""
        cost = groq_provider.estimate_cost(1000, "llama-3.1-70b-versatile")
        # Larger model costs more but still cheap
        assert cost > 0
        assert cost < 0.01  # < $0.01 per 1K tokens

    def test_estimate_cost_mixtral(self, groq_provider):
        """Test cost estimation for Mixtral."""
        cost = groq_provider.estimate_cost(1000, "mixtral-8x7b-32768")
        assert cost > 0
        assert cost < 0.001  # Very cheap

    def test_estimate_cost_gemma(self, groq_provider):
        """Test cost estimation for Gemma."""
        cost = groq_provider.estimate_cost(1000, "gemma2-9b-it")
        assert cost > 0
        assert cost < 0.001  # Very cheap

    def test_estimate_cost_unknown_model(self, groq_provider):
        """Test cost estimation for unknown model."""
        cost = groq_provider.estimate_cost(1000, "unknown-model")
        # Unknown models default to basic pricing
        assert cost >= 0  # Returns fallback pricing

    def test_calculate_confidence_stop(self, groq_provider):
        """Test confidence calculation with stop finish_reason."""
        metadata = {"choices": [{"finish_reason": "stop"}]}
        confidence = groq_provider.calculate_confidence("This is a complete response.", metadata)
        # With stop finish_reason, should have reasonable confidence
        # Base confidence (~0.4-0.6) + boost (+0.1) = ~0.5-0.7
        assert confidence >= 0.5
        assert confidence <= 1.0
        assert isinstance(confidence, float)

    def test_calculate_confidence_length(self, groq_provider):
        """Test confidence calculation with length finish_reason."""
        metadata = {"choices": [{"finish_reason": "length"}]}
        confidence = groq_provider.calculate_confidence("This is an incomplete", metadata)
        # With length finish_reason, confidence should be reduced
        assert confidence < 0.9
        assert confidence >= 0.0
        assert isinstance(confidence, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
