"""
Tests for Together provider with native logprobs support.

Run with:
    pytest tests/test_together_logprobs.py -v -s
"""

import os

import pytest
from cascadeflow.exceptions import ProviderError

from cascadeflow.providers.together import TogetherProvider

pytestmark = pytest.mark.skipif(
    not os.getenv("TOGETHER_API_KEY"), reason="TOGETHER_API_KEY not set - skipping real API tests"
)


@pytest.fixture
def provider():
    """Create Together provider instance."""
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        pytest.skip("TOGETHER_API_KEY not set")
    return TogetherProvider(api_key=api_key)


@pytest.fixture
def test_model():
    """Return test model - FIXED to use correct Together.ai model."""
    # ✅ CORRECT: Together.ai's fast Llama 3.1 model
    return "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"

    # ❌ WRONG (previous): "meta-llama/Llama-3-8b-chat-hf"
    # This model doesn't exist on Together.ai!


class TestTogetherBasics:
    """Test basic Together functionality."""

    @pytest.mark.asyncio
    async def test_provider_initialization(self, provider):
        """Test provider initializes correctly."""
        print("\n=== Testing Together Initialization ===")
        assert provider is not None
        assert provider.supports_logprobs()
        print("✓ Provider initialized")

    @pytest.mark.asyncio
    async def test_supports_logprobs(self, provider):
        """Test logprobs support check."""
        print("\n=== Testing Logprobs Support ===")
        supports = provider.supports_logprobs()
        print(f"Native logprobs support: {supports}")
        assert supports
        print("✓ Logprobs support confirmed")

    @pytest.mark.asyncio
    async def test_basic_completion(self, provider, test_model):
        """Test basic completion."""
        print("\n=== Testing Basic Completion ===")

        result = await provider.complete(
            prompt="What is 2+2? Answer with just the number.",
            model=test_model,
            max_tokens=5,
            temperature=0.1,
        )

        print(f"Model: {test_model}")
        print(f"Response: {result.content}")
        print(f"Cost: ${result.cost:.6f}")
        print(f"Tokens: {result.tokens_used}")
        print(f"Latency: {result.latency_ms:.0f}ms")

        assert result.content is not None
        assert len(result.content) > 0
        assert result.provider == "together"
        assert result.model == test_model
        assert result.tokens_used > 0

        print("✓ Basic completion works")


class TestTogetherLogprobs:
    """Test logprobs functionality."""

    @pytest.mark.asyncio
    async def test_logprobs_request(self, provider, test_model):
        """Test logprobs extraction."""
        print("\n=== Testing Logprobs ===")

        result = await provider.complete(
            prompt="The capital of France is",
            model=test_model,
            max_tokens=3,
            temperature=0.7,
            logprobs=True,
            top_logprobs=5,
        )

        print(f"Response: {result.content}")
        print(f"Has tokens: {result.tokens is not None}")
        print(f"Has logprobs: {result.logprobs is not None}")
        print(f"Has top_logprobs: {result.top_logprobs is not None}")

        if result.tokens:
            print(f"Tokens: {result.tokens[:3]}")  # First 3 tokens
            print(f"Confidence: {result.confidence:.3f}")
            if result.logprobs:
                print(f"Sample logprobs: {result.logprobs[:3]}")
            if result.top_logprobs:
                print(
                    f"Top alternatives for first token: {list(result.top_logprobs[0].keys())[:3]}"
                )

        # Verify logprobs are present
        assert result.tokens is not None
        assert len(result.tokens) > 0
        assert result.logprobs is not None
        assert len(result.logprobs) == len(result.tokens)
        assert result.top_logprobs is not None

        # Verify metadata
        assert result.metadata.get("has_logprobs")
        assert not result.metadata.get("estimated")  # Native logprobs

        print("✓ Together logprobs working")

    @pytest.mark.asyncio
    async def test_logprobs_without_top_k(self, provider, test_model):
        """Test logprobs without top_k alternatives."""
        print("\n=== Testing Logprobs (no top_k) ===")

        result = await provider.complete(
            prompt="Hello",
            model=test_model,
            max_tokens=5,
            logprobs=True,
            # No top_logprobs parameter
        )

        print(f"Response: {result.content}")
        print(f"Has logprobs: {result.logprobs is not None}")

        assert result.tokens is not None
        assert result.logprobs is not None
        # top_logprobs might be None or empty lists

        print("✓ Logprobs work without top_k")


@pytest.mark.asyncio
async def test_together_workflow(provider, test_model):
    """Complete workflow test."""
    print("\n" + "=" * 60)
    print("TOGETHER PROVIDER - WORKFLOW TEST")
    print("=" * 60)

    print("\n1. Basic completion (no logprobs)...")
    result1 = await provider.complete(
        prompt="Say hello", model=test_model, max_tokens=5, temperature=0.7
    )
    print(f"   Response: {result1.content}")
    print(f"   Cost: ${result1.cost:.6f}")
    assert result1.content is not None

    print("\n2. With logprobs...")
    result2 = await provider.complete(
        prompt="Count: one, two,",
        model=test_model,
        max_tokens=5,
        temperature=0.7,
        logprobs=True,
        top_logprobs=3,
    )
    print(f"   Response: {result2.content}")
    print(f"   Has logprobs: {result2.logprobs is not None}")
    print(f"   Confidence: {result2.confidence:.3f}")
    assert result2.logprobs is not None

    print("\n3. Different temperature...")
    result3 = await provider.complete(
        prompt="Write a random word:",
        model=test_model,
        max_tokens=3,
        temperature=1.0,  # Higher temperature
        logprobs=True,
    )
    print(f"   Response: {result3.content}")
    print(f"   Confidence: {result3.confidence:.3f}")

    print("\n" + "=" * 60)
    print("✓ TOGETHER READY!")
    print("=" * 60)


@pytest.mark.asyncio
async def test_error_handling(provider):
    """Test error handling."""
    print("\n=== Testing Error Handling ===")

    # Test with invalid model
    with pytest.raises(ProviderError) as exc_info:
        await provider.complete(prompt="Test", model="invalid-model-name", max_tokens=5)

    print(f"✓ Caught error for invalid model: {str(exc_info.value)[:100]}")
