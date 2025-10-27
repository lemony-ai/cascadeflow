"""Tests for Together.ai provider."""

import os
from unittest.mock import MagicMock, patch

import pytest

from cascadeflow.providers.base import ModelResponse
from cascadeflow.providers.together import TogetherProvider


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"TOGETHER_API_KEY": "test_key"}):
        yield


@pytest.fixture
def together_provider(mock_env):
    """Create Together.ai provider for testing."""
    return TogetherProvider()


@pytest.fixture
def mock_together_response():
    """Mock successful Together.ai API response."""
    return {
        "choices": [{"message": {"content": "This is a test response."}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


class TestTogetherProvider:
    """Tests for Together.ai provider."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        provider = TogetherProvider(api_key="explicit_key")
        assert provider.api_key == "explicit_key"

    def test_init_from_env(self, mock_env):
        """Test initialization from environment variable."""
        provider = TogetherProvider()
        assert provider.api_key == "test_key"

    def test_init_no_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Together.ai API key not found"):
                TogetherProvider()

    @pytest.mark.asyncio
    async def test_complete_success(self, together_provider, mock_together_response):
        """Test successful completion."""
        with patch.object(together_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_together_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await together_provider.complete(
                prompt="Test prompt", model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
            )

            assert isinstance(result, ModelResponse)
            assert result.content == "This is a test response."
            assert result.model == "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
            assert result.provider == "together"
            assert result.tokens_used == 30

    def test_estimate_cost_8b(self, together_provider):
        """Test cost estimation for 8B model."""
        cost = together_provider.estimate_cost(1000, "Llama-3.1-8B-Instruct-Turbo")
        # Uses blended pricing
        assert 0.00015 < cost < 0.00025  # Approximately $0.0002 per 1K tokens

    def test_estimate_cost_70b(self, together_provider):
        """Test cost estimation for 70B model."""
        cost = together_provider.estimate_cost(1000, "Llama-3.1-70B-Instruct-Turbo")
        # Uses blended pricing
        assert 0.0007 < cost < 0.0010  # Approximately $0.0008 per 1K tokens


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
