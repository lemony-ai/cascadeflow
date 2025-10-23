"""Tests for vLLM provider."""

import os
from unittest.mock import MagicMock, patch

import pytest
from cascadeflow.exceptions import ModelError, ProviderError

from cascadeflow.providers.base import ModelResponse
from cascadeflow.providers.vllm import VLLMProvider


@pytest.fixture
def vllm_provider():
    """Create vLLM provider for testing."""
    return VLLMProvider(base_url="http://localhost:8000/v1")


@pytest.fixture
def mock_vllm_response():
    """Mock successful vLLM API response."""
    return {
        "choices": [
            {"message": {"content": "This is a test response from vLLM."}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


class TestVLLMProvider:
    """Tests for vLLM provider."""

    def test_init_default_url(self):
        """Test initialization with default URL."""
        provider = VLLMProvider()
        assert provider.base_url == "http://localhost:8000/v1"

    def test_init_custom_url(self):
        """Test initialization with custom URL."""
        provider = VLLMProvider(base_url="http://custom:8000/v1")
        assert provider.base_url == "http://custom:8000/v1"

    def test_init_from_env(self):
        """Test initialization from environment variable."""
        with patch.dict(os.environ, {"VLLM_BASE_URL": "http://env:8000/v1"}):
            provider = VLLMProvider()
            assert provider.base_url == "http://env:8000/v1"

    @pytest.mark.asyncio
    async def test_complete_success(self, vllm_provider, mock_vllm_response):
        """Test successful completion."""
        with patch.object(vllm_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_vllm_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await vllm_provider.complete(
                prompt="Test prompt", model="meta-llama/Llama-3-8B-Instruct"
            )

            assert isinstance(result, ModelResponse)
            assert result.content == "This is a test response from vLLM."
            assert result.model == "meta-llama/Llama-3-8B-Instruct"
            assert result.provider == "vllm"
            assert result.cost == 0.0  # Self-hosted
            assert result.tokens_used == 30

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, vllm_provider, mock_vllm_response):
        """Test completion with system prompt."""
        with patch.object(vllm_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_vllm_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await vllm_provider.complete(
                prompt="Test", model="test-model", system_prompt="You are a helpful assistant."
            )

            # Verify system prompt was included
            call_args = mock_post.call_args
            messages = call_args[1]["json"]["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_complete_model_not_found(self, vllm_provider):
        """Test handling of model not found error."""
        with patch.object(vllm_provider.client, "post") as mock_post:
            import httpx

            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_post.side_effect = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )

            with pytest.raises(ModelError, match="not found"):
                await vllm_provider.complete("Test", "nonexistent-model")

    @pytest.mark.asyncio
    async def test_complete_server_overloaded(self, vllm_provider):
        """Test handling of server overload."""
        with patch.object(vllm_provider.client, "post") as mock_post:
            import httpx

            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_post.side_effect = httpx.HTTPStatusError(
                "Service Unavailable", request=MagicMock(), response=mock_response
            )

            with pytest.raises(ProviderError, match="overloaded"):
                await vllm_provider.complete("Test", "test-model")

    def test_estimate_cost(self, vllm_provider):
        """Test cost estimation (always 0 for vLLM)."""
        cost = vllm_provider.estimate_cost(1000, "any-model")
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_list_models(self, vllm_provider):
        """Test listing available models."""
        with patch.object(vllm_provider.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {"id": "meta-llama/Llama-3-8B-Instruct"},
                    {"id": "mistralai/Mistral-7B-Instruct-v0.2"},
                ]
            }
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            models = await vllm_provider.list_models()

            assert len(models) == 2
            assert "meta-llama/Llama-3-8B-Instruct" in models


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
