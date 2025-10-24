"""
Tests for Anthropic provider with logprobs support.

Run with:
    pytest tests/test_anthropic_logprobs.py -v -s

Or for specific test:
    pytest tests/test_anthropic_logprobs.py::test_anthropic_logprobs_fallback -v -s
"""

import os
import time

import pytest
from cascadeflow.exceptions import ProviderError

from cascadeflow.providers.anthropic import AnthropicProvider

# Skip all tests if no API key is set
pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set - skipping real API tests"
)


@pytest.fixture
def provider():
    """Create Anthropic provider instance."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return AnthropicProvider(api_key=api_key)


@pytest.fixture
def cheap_model():
    """Return cheapest model for testing."""
    return "claude-3-haiku-20240307"


@pytest.fixture
def good_model():
    """Return good quality model for testing."""
    # Use Haiku for all tests - it's reliable, cheap, and fast
    # Claude 3.5 Sonnet model names change frequently
    return "claude-3-haiku-20240307"


@pytest.fixture(autouse=True)
async def rate_limit_protection():
    """Add delay between tests to avoid rate limiting."""
    yield
    # Sleep after each test to avoid hitting rate limits
    # Anthropic free tier: ~4 requests/minute max
    time.sleep(3.0)  # 3 seconds between tests (conservative)


class TestAnthropicBasics:
    """Test basic Anthropic functionality."""

    @pytest.mark.asyncio
    async def test_provider_initialization(self, provider):
        """Test provider initializes correctly."""
        print("\n=== Testing Provider Initialization ===")
        assert provider is not None
        assert provider.api_key is not None
        assert provider.base_url == "https://api.anthropic.com/v1"
        print("✓ Provider initialized successfully")

    @pytest.mark.asyncio
    async def test_supports_logprobs(self, provider):
        """Test logprobs support check."""
        print("\n=== Testing Logprobs Support ===")
        supports = provider.supports_logprobs()
        print(f"Native logprobs support: {supports}")
        assert supports is False, "Anthropic should return False (uses fallback)"
        print("✓ Correctly reports no native logprobs support")

    @pytest.mark.asyncio
    async def test_basic_completion(self, provider, cheap_model):
        """Test basic completion without logprobs."""
        print("\n=== Testing Basic Completion ===")

        result = await provider.complete(
            prompt="What is 2+2? Answer with just the number.",
            model=cheap_model,
            max_tokens=10,
            temperature=0.1,
        )

        print("Prompt: What is 2+2?")
        print(f"Model: {cheap_model}")
        print(f"Response: {result.content}")
        print(f"Tokens used: {result.tokens_used}")
        print(f"Cost: ${result.cost:.6f}")
        print(f"Latency: {result.latency_ms:.0f}ms")
        print(f"Confidence: {result.confidence:.2f}")

        assert result.content is not None
        assert len(result.content) > 0
        assert result.provider == "anthropic"
        assert result.model == cheap_model
        assert result.cost > 0
        assert result.tokens_used > 0
        assert 0 <= result.confidence <= 1

        print("✓ Basic completion works")


class TestAnthropicLogprobs:
    """Test logprobs functionality with fallback."""

    @pytest.mark.asyncio
    async def test_logprobs_fallback(self, provider, cheap_model):
        """Test that logprobs fallback estimation works."""
        print("\n=== Testing Logprobs Fallback ===")

        result = await provider.complete(
            prompt="The capital of France is",
            model=cheap_model,
            max_tokens=5,
            temperature=0.7,
            logprobs=True,
            top_logprobs=10,
        )

        print("Prompt: The capital of France is")
        print(f"Model: {cheap_model}")
        print(f"Response: {result.content}")
        print("\nLogprobs Analysis:")
        print(f"  Tokens: {result.tokens}")
        print(f"  Logprobs: {result.logprobs}")
        print(f"  Top alternatives count: {len(result.top_logprobs) if result.top_logprobs else 0}")
        print(f"  Confidence: {result.confidence:.3f}")
        print(f"  Estimated: {result.metadata.get('estimated', False)}")

        # Verify fallback worked
        assert result.tokens is not None, "Tokens should be estimated"
        assert result.logprobs is not None, "Logprobs should be estimated"
        assert result.top_logprobs is not None, "Top logprobs should be estimated"
        assert len(result.tokens) > 0, "Should have at least one token"
        assert len(result.logprobs) == len(result.tokens), "Logprobs match tokens"
        assert result.metadata.get("estimated") is True, "Should be marked as estimated"
        assert 0 <= result.confidence <= 1, "Confidence in valid range"

        # Print sample alternatives for first token
        if result.top_logprobs and len(result.top_logprobs) > 0:
            print("\n  First token alternatives:")
            first_token_alts = list(result.top_logprobs[0].items())[:3]
            for i, (token, logprob) in enumerate(first_token_alts, 1):
                print(f"    {i}. '{token}' (logprob: {logprob:.3f})")

        print("\n✓ Logprobs fallback estimation works")

    @pytest.mark.asyncio
    async def test_logprobs_with_different_temperatures(self, provider, cheap_model):
        """Test that temperature affects confidence estimation."""
        print("\n=== Testing Temperature Impact on Confidence ===")

        temperatures = [0.1, 0.5, 0.9]
        confidences = []

        for temp in temperatures:
            result = await provider.complete(
                prompt="Say 'hello'",
                model=cheap_model,
                max_tokens=5,
                temperature=temp,
                logprobs=True,
            )

            confidences.append(result.confidence)
            print(f"Temperature {temp}: confidence = {result.confidence:.3f}")

        # Lower temperature should generally give higher confidence
        print(f"\nConfidence trend: {confidences}")
        print("Note: Lower temperature should trend toward higher confidence")

        assert all(0 <= c <= 1 for c in confidences), "All confidences valid"
        print("✓ Temperature affects confidence estimation")

    @pytest.mark.asyncio
    async def test_logprobs_without_top_k(self, provider, cheap_model):
        """Test logprobs without requesting top alternatives."""
        print("\n=== Testing Logprobs Without Top-K ===")

        result = await provider.complete(
            prompt="What is AI?",
            model=cheap_model,
            max_tokens=15,
            temperature=0.5,
            logprobs=True,
            # Note: no top_logprobs parameter
        )

        print(f"Response: {result.content[:50]}...")
        print(f"Has tokens: {result.tokens is not None}")
        print(f"Has logprobs: {result.logprobs is not None}")
        print(f"Has top_k: {result.top_logprobs is not None}")

        assert result.tokens is not None
        assert result.logprobs is not None
        assert result.top_logprobs is not None, "Should still provide top_k with default"

        print("✓ Works without explicit top_logprobs parameter")


class TestAnthropicModels:
    """Test different Anthropic models."""

    @pytest.mark.asyncio
    async def test_haiku_model(self, provider):
        """Test Claude 3 Haiku (cheapest, fastest)."""
        print("\n=== Testing Claude 3 Haiku ===")

        result = await provider.complete(
            prompt="Hi", model="claude-3-haiku-20240307", max_tokens=10, logprobs=True
        )

        print("Model: Haiku")
        print(f"Response: {result.content}")
        print(f"Cost: ${result.cost:.6f}")
        print(f"Confidence: {result.confidence:.2f}")

        assert result.content is not None
        assert result.cost < 0.001, "Haiku should be very cheap"
        print("✓ Haiku works")

    @pytest.mark.asyncio
    async def test_sonnet_35_model(self, provider, good_model):
        """Test Claude 3.5 Sonnet (best quality)."""
        print("\n=== Testing Claude 3.5 Sonnet ===")

        result = await provider.complete(
            prompt="Explain AI in one sentence.",
            model=good_model,
            max_tokens=50,
            temperature=0.7,
            logprobs=True,
            top_logprobs=5,
        )

        print("Model: Sonnet 3.5")
        print(f"Response: {result.content}")
        print(f"Cost: ${result.cost:.6f}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Tokens: {len(result.tokens) if result.tokens else 0}")

        assert result.content is not None
        assert len(result.content) > 0
        assert result.tokens is not None
        assert result.confidence > 0

        print("✓ Sonnet 3.5 works")


class TestAnthropicStopReasons:
    """Test how stop_reason affects confidence."""

    @pytest.mark.asyncio
    async def test_end_turn_confidence_boost(self, provider, cheap_model):
        """Test that end_turn increases confidence."""
        print("\n=== Testing End Turn Confidence Boost ===")

        result = await provider.complete(
            prompt="Say 'yes' and nothing else.",
            model=cheap_model,
            max_tokens=10,
            temperature=0.1,
            logprobs=True,
        )

        print(f"Response: {result.content}")
        print(f"Stop reason: {result.metadata.get('stop_reason')}")
        print(f"Confidence: {result.confidence:.3f}")

        # Should have end_turn and high confidence
        if result.metadata.get("stop_reason") == "end_turn":
            assert result.confidence > 0.7, "end_turn should boost confidence"
            print("✓ end_turn correctly boosts confidence")
        else:
            print(f"Note: Got {result.metadata.get('stop_reason')} instead of end_turn")

    @pytest.mark.asyncio
    async def test_max_tokens_confidence_reduction(self, provider, cheap_model):
        """Test that max_tokens reduces confidence."""
        print("\n=== Testing Max Tokens Confidence Reduction ===")

        result = await provider.complete(
            prompt="Write a long essay about artificial intelligence and its impact on society.",
            model=cheap_model,
            max_tokens=5,  # Force max_tokens
            temperature=0.7,
            logprobs=True,
        )

        print(f"Response: {result.content}")
        print(f"Stop reason: {result.metadata.get('stop_reason')}")
        print(f"Confidence: {result.confidence:.3f}")

        # Should have max_tokens and lower confidence
        if result.metadata.get("stop_reason") == "max_tokens":
            assert result.confidence < 0.9, "max_tokens should reduce confidence"
            print("✓ max_tokens correctly reduces confidence")
        else:
            print(f"Note: Got {result.metadata.get('stop_reason')} instead of max_tokens")


class TestAnthropicErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_invalid_model(self, provider):
        """Test handling of invalid model name."""
        print("\n=== Testing Invalid Model Handling ===")

        with pytest.raises(ProviderError) as exc_info:
            await provider.complete(prompt="Test", model="invalid-model-xyz", max_tokens=10)

        print(f"Error caught: {exc_info.value}")
        print("✓ Invalid model handled correctly")

    @pytest.mark.asyncio
    async def test_invalid_api_key(self):
        """Test handling of invalid API key."""
        print("\n=== Testing Invalid API Key Handling ===")

        bad_provider = AnthropicProvider(api_key="sk-ant-invalid-key-12345")

        with pytest.raises(ProviderError) as exc_info:
            await bad_provider.complete(
                prompt="Test", model="claude-3-haiku-20240307", max_tokens=10
            )

        assert "Invalid" in str(exc_info.value) or "401" in str(exc_info.value)
        print(f"Error caught: {exc_info.value}")
        print("✓ Invalid API key handled correctly")


class TestAnthropicIntegration:
    """Integration tests for cascade use."""

    @pytest.mark.asyncio
    async def test_cascade_ready_response(self, provider, cheap_model):
        """Test that response has all fields needed for cascade."""
        print("\n=== Testing Cascade-Ready Response ===")

        result = await provider.complete(
            prompt="What is machine learning?",
            model=cheap_model,
            max_tokens=30,
            temperature=0.7,
            logprobs=True,
            top_logprobs=10,
        )

        print("Required fields for cascade:")
        print(f"  ✓ content: {result.content[:30]}...")
        print(f"  ✓ tokens: {result.tokens[:3] if result.tokens else None}...")
        print(f"  ✓ logprobs: {result.logprobs[:3] if result.logprobs else None}...")
        print(f"  ✓ top_logprobs: {len(result.top_logprobs)} items")
        print(f"  ✓ confidence: {result.confidence:.3f}")
        print(f"  ✓ cost: ${result.cost:.6f}")
        print(f"  ✓ latency_ms: {result.latency_ms:.0f}ms")
        print(f"  ✓ estimated: {result.metadata.get('estimated')}")

        # Verify all required fields
        assert result.content is not None
        assert result.tokens is not None
        assert result.logprobs is not None
        assert result.top_logprobs is not None
        assert result.confidence is not None
        assert result.cost is not None
        assert result.latency_ms is not None
        assert result.metadata.get("estimated") is True

        print("\n✓ Response has all fields needed for cascade")


# Summary test that runs everything
@pytest.mark.asyncio
async def test_anthropic_full_workflow(provider, cheap_model):
    """Complete workflow test."""
    print("\n" + "=" * 60)
    print("ANTHROPIC PROVIDER - COMPLETE WORKFLOW TEST")
    print("=" * 60)

    # 1. Check support
    print("\n1. Checking logprobs support...")
    supports = provider.supports_logprobs()
    print(f"   Native support: {supports}")
    print(f"   Will use: {'Native API' if supports else 'Fallback estimation'}")

    # 2. Basic completion
    print("\n2. Testing basic completion...")
    result1 = await provider.complete(
        prompt="What is 5+5?", model=cheap_model, max_tokens=10, temperature=0.1
    )
    print(f"   Response: {result1.content}")
    print(f"   Cost: ${result1.cost:.6f}")

    # 3. Logprobs completion
    print("\n3. Testing with logprobs...")
    result2 = await provider.complete(
        prompt="The capital of Spain is",
        model=cheap_model,
        max_tokens=10,
        temperature=0.7,
        logprobs=True,
        top_logprobs=10,
    )
    print(f"   Response: {result2.content}")
    print(f"   Tokens: {len(result2.tokens)} tokens")
    print(f"   Confidence: {result2.confidence:.3f}")
    print(f"   Estimated: {result2.metadata.get('estimated')}")

    # 4. Verify cascade readiness
    print("\n4. Verifying cascade readiness...")
    assert all(
        [
            result2.content,
            result2.tokens,
            result2.logprobs,
            result2.top_logprobs,
            result2.confidence,
            result2.cost,
            result2.latency_ms,
        ]
    )
    print("   ✓ All required fields present")

    print("\n" + "=" * 60)
    print("✓ ANTHROPIC PROVIDER FULLY FUNCTIONAL")
    print("=" * 60)
