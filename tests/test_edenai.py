"""Tests for Eden AI provider."""

import os
from unittest.mock import MagicMock, patch

import pytest
from cascadeflow.exceptions import ProviderError

from cascadeflow.providers.base import ModelResponse, RetryConfig
from cascadeflow.providers.edenai import EdenAIProvider


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"EDENAI_API_KEY": "eden_test_key_12345"}):
        yield


@pytest.fixture
def edenai_provider(mock_env):
    """Create Eden AI provider for testing."""
    return EdenAIProvider()


@pytest.fixture
def mock_edenai_response():
    """Mock successful Eden AI API response (includes the per-request cost field)."""
    return {
        "model": "anthropic/claude-sonnet-4-5",
        "choices": [
            {
                "message": {"content": "This is a test response from Eden AI."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "cost": 1.23e-5,
    }


class TestEdenAIProvider:
    """Tests for Eden AI provider."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        provider = EdenAIProvider(api_key="eden_explicit_key")
        assert provider.api_key == "eden_explicit_key"

    def test_init_from_env(self, mock_env):
        """Test initialization from environment variable."""
        provider = EdenAIProvider()
        assert provider.api_key == "eden_test_key_12345"

    def test_init_default_base_url(self, edenai_provider):
        """Test the default base URL is the Eden AI v3 endpoint."""
        assert edenai_provider.base_url == "https://api.edenai.run/v3"

    def test_init_no_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Eden AI API key not found"):
                EdenAIProvider()

    @pytest.mark.asyncio
    async def test_complete_success(self, edenai_provider, mock_edenai_response):
        """Test successful completion, including cost read from the API response."""
        with patch.object(edenai_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_edenai_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await edenai_provider.complete(
                prompt="Test prompt", model="anthropic/claude-sonnet-4-5"
            )

            assert isinstance(result, ModelResponse)
            assert result.content == "This is a test response from Eden AI."
            assert result.model == "anthropic/claude-sonnet-4-5"
            assert result.provider == "edenai"
            assert result.tokens_used == 30
            # Cost comes straight from the API's "cost" field.
            assert result.cost == pytest.approx(1.23e-5)
            assert 0 <= result.confidence <= 1

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, edenai_provider, mock_edenai_response):
        """Test completion with system prompt builds the right messages."""
        with patch.object(edenai_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_edenai_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await edenai_provider.complete(
                prompt="Test",
                model="openai/gpt-5.1",
                system_prompt="You are a helpful assistant.",
            )

            call_args = mock_post.call_args
            messages = call_args[1]["json"]["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_complete_falls_back_to_local_pricing(self, edenai_provider):
        """When the API omits cost, the local pricing table is used."""
        response_without_cost = {
            "model": "anthropic/claude-sonnet-4-5",
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 1000, "total_tokens": 2000},
        }
        with patch.object(edenai_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = response_without_cost
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await edenai_provider.complete(
                prompt="Test", model="anthropic/claude-sonnet-4-5"
            )
            # 1000 in + 1000 out at 3.0/15.0 per 1M = 0.003 + 0.015
            assert result.cost == pytest.approx(0.018)

    @pytest.mark.asyncio
    async def test_complete_invalid_key(self, mock_env):
        """Test handling of 401 auth errors."""
        provider = EdenAIProvider(retry_config=RetryConfig(max_attempts=1))
        with patch.object(provider.client, "post") as mock_post:
            import httpx

            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "unauthorized"
            mock_post.side_effect = httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response
            )

            with pytest.raises(ProviderError, match="Invalid Eden AI API key"):
                await provider.complete("Test", "anthropic/claude-haiku-4-5")

    @pytest.mark.asyncio
    async def test_complete_rate_limit(self, mock_env):
        """Test handling of 429 rate limit errors."""
        provider = EdenAIProvider(retry_config=RetryConfig(max_attempts=1))
        with patch.object(provider.client, "post") as mock_post:
            import httpx

            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.text = "too many requests"
            mock_post.side_effect = httpx.HTTPStatusError(
                "Too Many Requests", request=MagicMock(), response=mock_response
            )

            with pytest.raises(ProviderError, match="rate limit"):
                await provider.complete("Test", "anthropic/claude-haiku-4-5")

    def test_estimate_cost_known_model(self, edenai_provider):
        """Test cost estimation for a known model."""
        cost = edenai_provider.estimate_cost(1000, "anthropic/claude-sonnet-4-5")
        assert cost > 0
        assert cost < 0.01

    def test_estimate_cost_unknown_model(self, edenai_provider):
        """Test cost estimation falls back for unknown models."""
        cost = edenai_provider.estimate_cost(1000, "unknown/model")
        assert cost >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
