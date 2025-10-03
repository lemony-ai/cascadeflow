"""Tests for HuggingFace, Together.ai, and vLLM providers."""

import pytest
from unittest.mock import MagicMock, patch
import os

from cascadeflow.providers.huggingface import HuggingFaceProvider
from cascadeflow.providers.together import TogetherProvider
from cascadeflow.providers.vllm import VLLMProvider
from cascadeflow.providers.base import ModelResponse


class TestHuggingFaceProvider:
    """Tests for HuggingFace provider."""

    def test_init(self):
        """Test initialization."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test"}):
            provider = HuggingFaceProvider()
            assert provider.api_key == "hf_test"

    def test_estimate_cost_small(self):
        """Test cost estimation for small models."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test"}):
            provider = HuggingFaceProvider()
            cost = provider.estimate_cost(1000, "codellama-7b")
            assert cost == 0.0  # Small models are free

    def test_estimate_cost_large(self):
        """Test cost estimation for large models."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test"}):
            provider = HuggingFaceProvider()
            cost = provider.estimate_cost(1000, "codellama-70b")
            assert cost > 0.0  # Large models have cost


class TestTogetherProvider:
    """Tests for Together.ai provider."""

    def test_init(self):
        """Test initialization."""
        with patch.dict(os.environ, {"TOGETHER_API_KEY": "test_key"}):
            provider = TogetherProvider()
            assert provider.api_key == "test_key"

    def test_estimate_cost(self):
        """Test cost estimation."""
        with patch.dict(os.environ, {"TOGETHER_API_KEY": "test_key"}):
            provider = TogetherProvider()
            cost = provider.estimate_cost(1000, "llama-70b")
            assert cost > 0.0
            assert cost < 0.002  # Cheaper than OpenAI


class TestVLLMProvider:
    """Tests for vLLM provider."""

    def test_init_default(self):
        """Test initialization with defaults."""
        provider = VLLMProvider()
        assert provider.base_url == "http://localhost:8000/v1"

    def test_init_custom_url(self):
        """Test initialization with custom URL."""
        provider = VLLMProvider(base_url="http://vllm:8000/v1")
        assert provider.base_url == "http://vllm:8000/v1"

    def test_estimate_cost(self):
        """Test cost estimation (should always be 0)."""
        provider = VLLMProvider()
        cost = provider.estimate_cost(1000, "any-model")
        assert cost == 0.0  # Self-hosted = free


if __name__ == "__main__":
    pytest.main([__file__, "-v"])