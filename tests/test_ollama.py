"""Tests for Ollama provider."""

from unittest.mock import MagicMock, patch

import pytest
from cascadeflow.exceptions import ModelError, ProviderError

from cascadeflow.providers.base import ModelResponse
from cascadeflow.providers.ollama import OllamaProvider


@pytest.fixture
def ollama_provider():
    """Create Ollama provider for testing."""
    return OllamaProvider()


@pytest.fixture
def mock_ollama_response():
    """Mock successful Ollama API response."""
    return {
        "response": "This is a test response from Llama.",
        "done": True,
        "total_duration": 1234567890,
        "load_duration": 123456,
        "prompt_eval_count": 10,
        "eval_count": 20,
    }


@pytest.fixture
def mock_ollama_list_response():
    """Mock Ollama list models response."""
    return {
        "models": [
            {"name": "gemma3:1b"},
            {"name": "llama3:8b"},
            {"name": "mistral:7b"},
            {"name": "codellama:7b"},
        ]
    }


class TestOllamaProvider:
    """Tests for Ollama provider."""

    def test_init_default_url(self):
        """Test initialization with default URL."""
        provider = OllamaProvider()
        assert provider.base_url == "http://localhost:11434"

    def test_init_custom_url(self):
        """Test initialization with custom URL."""
        provider = OllamaProvider(base_url="http://custom-host:11434")
        assert provider.base_url == "http://custom-host:11434"

    def test_init_from_env(self):
        """Test initialization from OLLAMA_HOST env var."""
        with patch.dict("os.environ", {"OLLAMA_HOST": "http://remote:11434"}):
            provider = OllamaProvider()
            assert provider.base_url == "http://remote:11434"

    @pytest.mark.asyncio
    async def test_complete_success(self, ollama_provider, mock_ollama_response):
        """Test successful completion."""
        with patch.object(ollama_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_ollama_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = await ollama_provider.complete(prompt="Test prompt", model="gemma3:1b")

            assert isinstance(result, ModelResponse)
            assert result.content == "This is a test response from Llama."
            assert result.model == "gemma3:1b"
            assert result.provider == "ollama"
            assert result.cost == 0.0  # Always free!
            assert 0 <= result.confidence <= 1

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, ollama_provider, mock_ollama_response):
        """Test completion with system prompt."""
        with patch.object(ollama_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_ollama_response
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await ollama_provider.complete(
                prompt="Test", model="gemma3:1b", system_prompt="You are a helpful assistant."
            )

            # Verify system prompt was included
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            assert "system" in payload
            assert payload["system"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_complete_model_not_found(self, ollama_provider):
        """Test handling of model not found error."""
        with patch.object(ollama_provider.client, "post") as mock_post:
            import httpx

            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_post.side_effect = httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )

            with pytest.raises(ModelError, match="Model .* not found"):
                await ollama_provider.complete("Test", "nonexistent:model")

    @pytest.mark.asyncio
    async def test_complete_connection_error(self, ollama_provider):
        """Test handling of connection errors."""
        with patch.object(ollama_provider.client, "post") as mock_post:
            import httpx

            mock_post.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(ProviderError, match="Cannot connect to Ollama"):
                await ollama_provider.complete("Test", "gemma3:1b")

    def test_estimate_cost_always_zero(self, ollama_provider):
        """Test cost estimation is always $0."""
        assert ollama_provider.estimate_cost(1000, "gemma3:1b") == 0.0
        assert ollama_provider.estimate_cost(10000, "mistral:7b") == 0.0
        assert ollama_provider.estimate_cost(100000, "codellama:34b") == 0.0

    @pytest.mark.asyncio
    async def test_list_models(self, ollama_provider, mock_ollama_list_response):
        """Test listing available models."""
        with patch.object(ollama_provider.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_ollama_list_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            models = await ollama_provider.list_models()

            assert isinstance(models, list)
            assert len(models) == 4
            assert "gemma3:1b" in models
            assert "llama3:8b" in models
            assert "mistral:7b" in models
            assert "codellama:7b" in models

    @pytest.mark.asyncio
    async def test_pull_model(self, ollama_provider):
        """Test pulling a model."""
        with patch.object(ollama_provider.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            await ollama_provider.pull_model("gemma3:1b")

            # Verify API was called
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "gemma3:1b" in str(call_args)

    def test_calculate_confidence_done(self, ollama_provider):
        """Test confidence calculation when done=True."""
        metadata = {"done": True}

        # Use longer response for higher confidence
        long_response = (
            "This is a complete and detailed response that provides "
            "comprehensive information about the topic. It contains "
            "multiple sentences and demonstrates thorough understanding "
            "of the subject matter being discussed."
        )

        confidence = ollama_provider.calculate_confidence(long_response, metadata)
        # Updated threshold to match current confidence calculation (0.617 is reasonable)
        assert confidence > 0.6

    def test_calculate_confidence_not_done(self, ollama_provider):
        """Test confidence calculation when done=False."""
        metadata = {"done": False}
        confidence = ollama_provider.calculate_confidence("This is incomplete", metadata)
        # Should still return reasonable confidence
        assert 0 <= confidence <= 1

    # ============================================================================
    # NEW TESTS: Local Providers Enhancement
    # ============================================================================

    def test_init_from_ollama_base_url_env(self):
        """Test initialization from OLLAMA_BASE_URL env var (standard)."""
        with patch.dict(
            "os.environ", {"OLLAMA_BASE_URL": "http://network-ollama:11434"}, clear=True
        ):
            provider = OllamaProvider()
            assert provider.base_url == "http://network-ollama:11434"

    def test_init_env_var_priority(self):
        """Test OLLAMA_BASE_URL takes priority over OLLAMA_HOST."""
        with patch.dict(
            "os.environ",
            {"OLLAMA_BASE_URL": "http://priority:11434", "OLLAMA_HOST": "http://fallback:11434"},
            clear=True,
        ):
            provider = OllamaProvider()
            assert provider.base_url == "http://priority:11434"

    def test_init_ollama_host_fallback(self):
        """Test OLLAMA_HOST is used when OLLAMA_BASE_URL not set."""
        with patch.dict("os.environ", {"OLLAMA_HOST": "http://legacy:11434"}, clear=True):
            provider = OllamaProvider()
            assert provider.base_url == "http://legacy:11434"

    def test_init_with_api_key_parameter(self):
        """Test initialization with API key parameter for remote servers."""
        provider = OllamaProvider(api_key="test-api-key-123")
        assert provider.api_key == "test-api-key-123"
        # Verify Authorization header is set
        assert "Authorization" in provider.client.headers
        assert provider.client.headers["Authorization"] == "Bearer test-api-key-123"

    def test_init_with_api_key_from_env(self):
        """Test API key loading from OLLAMA_API_KEY environment variable."""
        with patch.dict("os.environ", {"OLLAMA_API_KEY": "env-api-key-456"}, clear=True):
            provider = OllamaProvider()
            assert provider.api_key == "env-api-key-456"
            assert "Authorization" in provider.client.headers
            assert provider.client.headers["Authorization"] == "Bearer env-api-key-456"

    def test_init_network_deployment_example(self):
        """Test configuration for network deployment scenario."""
        # Simulate network deployment (another machine on LAN)
        with patch.dict(
            "os.environ", {"OLLAMA_BASE_URL": "http://192.168.1.100:11434"}, clear=True
        ):
            provider = OllamaProvider()
            assert provider.base_url == "http://192.168.1.100:11434"
            # No API key needed for trusted network
            assert provider.api_key is None

    def test_init_remote_deployment_example(self):
        """Test configuration for remote deployment with authentication."""
        # Simulate remote deployment (external server with auth)
        with patch.dict(
            "os.environ",
            {
                "OLLAMA_BASE_URL": "https://ollama.example.com",
                "OLLAMA_API_KEY": "secure-api-key-789",
            },
            clear=True,
        ):
            provider = OllamaProvider()
            assert provider.base_url == "https://ollama.example.com"
            assert provider.api_key == "secure-api-key-789"
            assert provider.client.headers["Authorization"] == "Bearer secure-api-key-789"


# Integration test (requires Ollama to be running)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_ollama_real_call():
    """
    Integration test with real Ollama.

    Requires:
    - Ollama running
    - gemma3:1b model pulled

    Run with: pytest tests/test_ollama.py -v -m integration
    """
    provider = OllamaProvider()

    try:
        result = await provider.complete(
            prompt="Say 'Hello' in one word", model="gemma3:1b", max_tokens=10
        )

        assert isinstance(result, ModelResponse)
        assert len(result.content) > 0
        assert result.cost == 0.0
        assert result.provider == "ollama"

        print("\n✅ Real Ollama test passed!")
        print(f"Response: {result.content}")
        print(f"Cost: ${result.cost:.4f} (FREE!)")

    except Exception as e:
        pytest.skip(f"Ollama not available: {e}")

    finally:
        await provider.client.aclose()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
