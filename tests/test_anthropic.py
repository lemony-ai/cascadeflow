"""Tests for Anthropic provider."""

import os
from unittest.mock import MagicMock, patch

import pytest

from cascadeflow.providers.anthropic import AnthropicProvider
from cascadeflow.providers.base import ModelResponse


@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"}):
        yield


@pytest.fixture
def anthropic_provider(mock_env):
    """Create Anthropic provider for testing."""
    return AnthropicProvider()


@pytest.fixture
def mock_anthropic_response():
    """Mock successful Anthropic API response."""
    return {
        "content": [{"text": "This is a test response from Claude."}],
        "stop_reason": "end_turn",
        "id": "msg_test_123",
    }


class TestAnthropicProvider:
    """Tests for Anthropic provider."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        provider = AnthropicProvider(api_key="sk-ant-explicit")
        assert provider.api_key == "sk-ant-explicit"

    def test_init_from_env(self, mock_env):
        """Test initialization from environment variable."""
        provider = AnthropicProvider()
        assert provider.api_key == "sk-ant-test-key"

    def test_init_no_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Anthropic API key not found"):
                AnthropicProvider()

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Mocking strategy needs update - client.post mock not working with current provider implementation"
    )
    async def test_complete_success(self, anthropic_provider, mock_anthropic_response):
        """Test successful completion."""
        with patch.object(anthropic_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_anthropic_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await anthropic_provider.complete(
                prompt="Test prompt", model="claude-3-sonnet-20240229"
            )

            assert isinstance(result, ModelResponse)
            assert result.content == "This is a test response from Claude."
            assert result.model == "claude-3-sonnet-20240229"
            assert result.provider == "anthropic"
            assert 0 <= result.confidence <= 1

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, anthropic_provider, mock_anthropic_response):
        """Test completion with system prompt."""
        with patch.object(anthropic_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_anthropic_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await anthropic_provider.complete(
                prompt="Test",
                model="claude-3-opus-20240229",
                system_prompt="You are a helpful assistant.",
            )

            # Verify system prompt was included
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert "system" in payload
            assert payload["system"] == "You are a helpful assistant."

    def test_estimate_cost_sonnet(self, anthropic_provider):
        """Test cost estimation for Claude 3 Sonnet."""
        cost = anthropic_provider.estimate_cost(1000, "claude-3-sonnet-20240229")
        # Uses blended pricing (input + output tokens)
        assert 0.008 < cost < 0.010  # Approximately $0.009/1K tokens

    def test_estimate_cost_opus(self, anthropic_provider):
        """Test cost estimation for Claude 3 Opus."""
        cost = anthropic_provider.estimate_cost(1000, "claude-3-opus-20240229")
        # Uses blended pricing
        assert 0.040 < cost < 0.050  # Approximately $0.045/1K tokens

    def test_estimate_cost_haiku(self, anthropic_provider):
        """Test cost estimation for Claude 3 Haiku."""
        cost = anthropic_provider.estimate_cost(1000, "claude-3-haiku-20240307")
        # Uses blended pricing
        assert 0.0005 < cost < 0.0010  # Approximately $0.00075/1K tokens


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
