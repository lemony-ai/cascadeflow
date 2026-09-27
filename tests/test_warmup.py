"""Tests for model warmup functionality."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cascadeflow import CascadeAgent
from cascadeflow.providers import OllamaProvider, VLLMProvider, OpenAIProvider
from cascadeflow.schema.config import ModelConfig


@pytest.mark.asyncio
async def test_base_provider_warmup_cloud():
    """Test that cloud providers skip warmup."""
    provider = OpenAIProvider(api_key="test-key")

    result = await provider.warmup(models=["gpt-4"])

    assert result["success"] is True
    assert result["models_warmed"] == []
    assert "message" in result
    assert "Cloud provider" in result["message"]


@pytest.mark.asyncio
async def test_ollama_warmup_single_model():
    """Test Ollama warmup with a single model."""
    provider = OllamaProvider()

    # Mock the HTTP client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch.object(provider.client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await provider.warmup(
            models=["llama3.2:1b"],
            warmup_prompt="test",
            warmup_config={"max_tokens": 1, "keep_alive": 3600}
        )

    assert result["success"] is True
    assert "llama3.2:1b" in result["models_warmed"]
    assert len(result["models_warmed"]) == 1
    assert result["errors"] == {}
    assert "keep_alive" in result


@pytest.mark.asyncio
async def test_ollama_warmup_multiple_models_parallel():
    """Test Ollama warmup with multiple models in parallel."""
    provider = OllamaProvider()

    # Mock the HTTP client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch.object(provider.client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await provider.warmup(
            models=["llama3.2:1b", "llama3.2:3b"],
            warmup_config={"parallel": True}
        )

    assert result["success"] is True
    assert len(result["models_warmed"]) == 2
    assert "llama3.2:1b" in result["models_warmed"]
    assert "llama3.2:3b" in result["models_warmed"]


@pytest.mark.asyncio
async def test_ollama_warmup_model_not_found():
    """Test Ollama warmup handles missing model gracefully."""
    provider = OllamaProvider()

    # Mock 404 response
    from httpx import HTTPStatusError, Response, Request
    mock_request = Request("POST", "http://test")
    mock_response = Response(404, request=mock_request)

    with patch.object(provider.client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = HTTPStatusError(
            "Not found",
            request=mock_request,
            response=mock_response
        )

        result = await provider.warmup(models=["nonexistent-model"])

    assert result["success"] is False
    assert len(result["models_warmed"]) == 0
    assert "nonexistent-model" in result["errors"]
    assert "Model not found" in result["errors"]["nonexistent-model"]


@pytest.mark.asyncio
async def test_vllm_warmup():
    """Test vLLM warmup."""
    provider = VLLMProvider(base_url="http://localhost:8000/v1")

    # Mock the HTTP client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch.object(provider.client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await provider.warmup(
            models=["meta-llama/Llama-3-8B-Instruct"],
            warmup_prompt="test"
        )

    assert result["success"] is True
    assert "meta-llama/Llama-3-8B-Instruct" in result["models_warmed"]


@pytest.mark.asyncio
async def test_cascade_agent_warmup():
    """Test CascadeAgent warmup orchestration."""
    # Create models with mixed providers
    cheap_model = ModelConfig(
        provider=OllamaProvider(),
        model="llama3.2:1b",
        cost=0.0,
        speed_ms=100,
        quality=0.6
    )

    expensive_model = ModelConfig(
        provider=OpenAIProvider(api_key="test-key"),
        model="gpt-4",
        cost=0.03,
        speed_ms=1000,
        quality=0.95
    )

    agent = CascadeAgent(models=[cheap_model, expensive_model])

    # Mock Ollama warmup
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch.object(cheap_model.provider.client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await agent.warmup()

    assert result["success"] is True
    assert result["total_models"] == 2
    assert result["models_warmed"] >= 1  # At least Ollama should warm up
    assert "results" in result
    assert len(result["results"]) == 2  # Two providers


@pytest.mark.asyncio
async def test_cascade_agent_warmup_parallel():
    """Test CascadeAgent warmup with parallel execution."""
    # Create multiple local models
    model1 = ModelConfig(
        provider=OllamaProvider(),
        model="llama3.2:1b",
        cost=0.0,
        speed_ms=100,
        quality=0.6
    )

    model2 = ModelConfig(
        provider=VLLMProvider(base_url="http://localhost:8000/v1"),
        model="mistral-7b",
        cost=0.0,
        speed_ms=150,
        quality=0.7
    )

    agent = CascadeAgent(models=[model1, model2])

    # Mock responses
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch.object(model1.provider.client, 'post', new_callable=AsyncMock) as mock1, \
         patch.object(model2.provider.client, 'post', new_callable=AsyncMock) as mock2:
        mock1.return_value = mock_response
        mock2.return_value = mock_response

        result = await agent.warmup(parallel=True)

    assert result["success"] is True
    assert result["total_models"] == 2


@pytest.mark.asyncio
async def test_warmup_custom_config():
    """Test warmup with custom configuration."""
    provider = OllamaProvider()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch.object(provider.client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        result = await provider.warmup(
            models=["llama3.2:1b"],
            warmup_prompt="custom prompt",
            warmup_config={
                "max_tokens": 5,
                "keep_alive": 7200,  # 2 hours
                "parallel": False
            }
        )

    assert result["success"] is True
    # Verify the call was made with custom config
    call_args = mock_post.call_args
    assert call_args is not None
    payload = call_args[1]["json"]
    assert payload["prompt"] == "custom prompt"
    assert payload["options"]["num_predict"] == 5
    assert payload["keep_alive"] == "7200s"


@pytest.mark.asyncio
async def test_warmup_idempotent():
    """Test that warmup can be called multiple times safely."""
    provider = OllamaProvider()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch.object(provider.client, 'post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        # Call warmup twice
        result1 = await provider.warmup(models=["llama3.2:1b"])
        result2 = await provider.warmup(models=["llama3.2:1b"])

    assert result1["success"] is True
    assert result2["success"] is True
    # Should have been called twice
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_warmup_no_models_specified():
    """Test warmup when no models are specified."""
    provider = OllamaProvider()

    # Mock list_models to return available models
    mock_list_response = MagicMock()
    mock_list_response.status_code = 200
    mock_list_response.raise_for_status = MagicMock()
    mock_list_response.json.return_value = {
        "models": [
            {"name": "llama3.2:1b"},
            {"name": "mistral:7b"}
        ]
    }

    mock_warmup_response = MagicMock()
    mock_warmup_response.status_code = 200
    mock_warmup_response.raise_for_status = MagicMock()

    with patch.object(provider.client, 'get', new_callable=AsyncMock) as mock_get, \
         patch.object(provider.client, 'post', new_callable=AsyncMock) as mock_post:
        mock_get.return_value = mock_list_response
        mock_post.return_value = mock_warmup_response

        result = await provider.warmup()  # No models specified

    assert result["success"] is True
    # Should warm up first available model
    assert len(result["models_warmed"]) == 1
    assert result["models_warmed"][0] == "llama3.2:1b"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
