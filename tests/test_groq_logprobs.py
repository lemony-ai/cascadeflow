"""
Tests for Groq provider with native logprobs support.

Run with:
    pytest tests/test_groq_logprobs.py -v -s
"""

import os

import pytest

from cascadeflow.providers.groq import GroqProvider

pytestmark = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"), reason="GROQ_API_KEY not set - skipping real API tests"
)


@pytest.fixture
def provider():
    """Create Groq provider instance."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY not set")
    return GroqProvider(api_key=api_key)


@pytest.fixture
def test_model():
    """Return test model - Groq's fastest."""
    return "llama-3.1-8b-instant"


class TestGroqBasics:
    """Test basic Groq functionality."""

    @pytest.mark.asyncio
    async def test_provider_initialization(self, provider):
        """Test provider initializes correctly."""
        print("\n=== Testing Groq Initialization ===")
        assert provider is not None
        print("✓ Provider initialized")

    @pytest.mark.asyncio
    async def test_supports_logprobs(self, provider):
        """Test logprobs support check."""
        print("\n=== Testing Logprobs Support ===")
        supports = provider.supports_logprobs()
        print(f"Native logprobs support: {supports}")
        # Note: Check your base.py PROVIDER_CAPABILITIES for Groq
        print(f"✓ Logprobs support: {supports}")

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
        print(f"Latency: {result.latency_ms:.0f}ms (Groq is FAST!)")

        assert result.content is not None
        assert result.provider == "groq"

        print("✓ Basic completion works")


class TestGroqLogprobs:
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
            print(f"Tokens: {result.tokens}")
            print(f"Logprobs: {result.logprobs}")
            print(f"Confidence: {result.confidence:.3f}")

        # Verify logprobs present (native or fallback)
        assert result.tokens is not None
        assert result.logprobs is not None

        print("✓ Groq logprobs working")


class TestGroqCascadeReady:
    """Test Groq is ready for cascade."""

    @pytest.mark.asyncio
    async def test_cascade_ready(self, provider, test_model):
        """Test cascade readiness."""
        print("\n=== Testing Cascade Readiness ===")

        result = await provider.complete(
            prompt="What is AI?",
            model=test_model,
            max_tokens=20,
            temperature=0.7,
            logprobs=True,
            top_logprobs=5,
        )

        print(f"✓ content: {result.content[:30]}...")
        print(f"✓ tokens: {len(result.tokens) if result.tokens else 0}")
        print(f"✓ cost: ${result.cost:.6f}")
        print(f"✓ latency: {result.latency_ms:.0f}ms")

        assert result.content is not None
        assert result.tokens is not None

        print("✓ Groq ready for cascade (VERY FAST inference!)")


@pytest.mark.asyncio
async def test_groq_full_workflow(provider, test_model):
    """Complete workflow test."""
    print("\n" + "=" * 60)
    print("GROQ PROVIDER - FULL WORKFLOW TEST")
    print("=" * 60)

    print("\n1. Basic completion...")
    result1 = await provider.complete(prompt="Hi", model=test_model, max_tokens=5, temperature=0.1)
    print(f"   Response: {result1.content}")
    print(f"   Speed: {result1.latency_ms:.0f}ms (FAST!)")

    print("\n2. With logprobs...")
    result2 = await provider.complete(
        prompt="Hello", model=test_model, max_tokens=3, temperature=0.7, logprobs=True
    )
    print(f"   Response: {result2.content}")
    print(f"   Has logprobs: {result2.logprobs is not None}")

    print("\n" + "=" * 60)
    print("✓ GROQ READY - FASTEST INFERENCE PROVIDER!")
    print("=" * 60)
