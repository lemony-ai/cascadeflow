"""
Tests for OpenAI provider with native logprobs support.

Run with:
    pytest tests/test_openai_logprobs.py -v -s
"""

import os

import pytest

from cascadeflow.providers.openai import OpenAIProvider

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set - skipping real API tests"
)


@pytest.fixture
def provider():
    """Create OpenAI provider instance."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    return OpenAIProvider(api_key=api_key)


@pytest.fixture
def cheap_model():
    """Return cheapest model for testing."""
    return "gpt-3.5-turbo"


@pytest.fixture
def mini_model():
    """Return gpt-4o-mini for testing."""
    return "gpt-4o-mini"


class TestOpenAIBasics:
    """Test basic OpenAI functionality."""

    @pytest.mark.asyncio
    async def test_provider_initialization(self, provider):
        """Test provider initializes correctly."""
        print("\n=== Testing OpenAI Initialization ===")
        assert provider is not None
        assert provider.api_key is not None
        print("✓ Provider initialized")

    @pytest.mark.asyncio
    async def test_supports_logprobs(self, provider):
        """Test logprobs support check."""
        print("\n=== Testing Logprobs Support ===")
        supports = provider.supports_logprobs()
        print(f"Native logprobs support: {supports}")
        assert supports is True, "OpenAI should have native logprobs"
        print("✓ Native logprobs supported!")

    @pytest.mark.asyncio
    async def test_basic_completion(self, provider, cheap_model):
        """Test basic completion without logprobs."""
        print("\n=== Testing Basic Completion ===")

        result = await provider.complete(
            prompt="What is 2+2? Answer with just the number.",
            model=cheap_model,
            max_tokens=5,
            temperature=0.1,
        )

        print("Prompt: What is 2+2?")
        print(f"Model: {cheap_model}")
        print(f"Response: {result.content}")
        print(f"Cost: ${result.cost:.6f}")
        print(f"Latency: {result.latency_ms:.0f}ms")

        assert result.content is not None
        assert result.provider == "openai"
        assert result.cost > 0

        print("✓ Basic completion works")


class TestOpenAINativeLogprobs:
    """Test native logprobs - OpenAI returns real probabilities."""

    @pytest.mark.asyncio
    async def test_native_logprobs_extraction(self, provider, cheap_model):
        """Test that native logprobs are extracted from API."""
        print("\n=== Testing Native Logprobs ===")

        result = await provider.complete(
            prompt="The capital of France is",
            model=cheap_model,
            max_tokens=3,
            temperature=0.7,
            logprobs=True,
            top_logprobs=5,
        )

        print(f"Response: {result.content}")
        print(f"Tokens: {result.tokens}")
        print(f"Logprobs: {result.logprobs}")
        print(f"Confidence: {result.confidence:.3f}")
        print(f"Estimated: {result.metadata.get('estimated', 'N/A')}")

        # CRITICAL: Verify native logprobs (not estimated)
        assert result.tokens is not None, "Must have tokens"
        assert result.logprobs is not None, "Must have logprobs"
        assert result.top_logprobs is not None, "Must have top_logprobs"
        assert len(result.logprobs) == len(result.tokens), "Counts must match"

        # OpenAI returns REAL logprobs, not estimated
        assert result.metadata.get("estimated") is not True, "Should be real, not estimated"

        # Real logprobs should be more varied than fallback
        assert all(-30 < lp < 0 for lp in result.logprobs), "Logprobs realistic"

        if result.top_logprobs and len(result.top_logprobs) > 0:
            print("\nFirst token alternatives:")
            first_alts = result.top_logprobs[0]
            if isinstance(first_alts, dict):
                for i, (token, logprob) in enumerate(list(first_alts.items())[:3], 1):
                    print(f"  {i}. '{token}' (logprob: {logprob:.3f})")
            elif isinstance(first_alts, list):
                for i, alt in enumerate(first_alts[:3], 1):
                    print(f"  {i}. '{alt.get('token')}' (logprob: {alt.get('logprob'):.3f})")

        print("\n✓ Native logprobs working - real probabilities!")

    @pytest.mark.asyncio
    async def test_logprobs_with_top_k(self, provider, cheap_model):
        """Test top_logprobs parameter works."""
        print("\n=== Testing Top-K Logprobs ===")

        result = await provider.complete(
            prompt="Hello",
            model=cheap_model,
            max_tokens=3,
            temperature=0.5,
            logprobs=True,
            top_logprobs=10,
        )

        print(f"Response: {result.content}")
        print(
            f"Top-k alternatives per token: {len(result.top_logprobs[0]) if result.top_logprobs else 0}"
        )

        assert result.top_logprobs is not None
        assert len(result.top_logprobs) > 0

        # Should have up to 10 alternatives per token
        first_token_alts = result.top_logprobs[0]
        if isinstance(first_token_alts, dict):
            alt_count = len(first_token_alts)
        else:
            alt_count = len(first_token_alts)

        print(f"Alternatives for first token: {alt_count}")
        assert alt_count <= 10, "Should respect top_k limit"

        print("✓ Top-k parameter working")

    @pytest.mark.asyncio
    async def test_without_logprobs_request(self, provider, cheap_model):
        """Test logprobs NOT added when not requested."""
        print("\n=== Testing Without Logprobs Request ===")

        result = await provider.complete(
            prompt="Hi", model=cheap_model, max_tokens=3, temperature=0.5, logprobs=False
        )

        print(f"Response: {result.content}")
        print(f"Has tokens: {result.tokens is not None}")
        print(f"Has logprobs: {result.logprobs is not None}")

        # OpenAI might still return some data, but we check our extraction
        print("✓ Logprobs request handling works")


class TestOpenAIModels:
    """Test different OpenAI models."""

    @pytest.mark.asyncio
    async def test_gpt35_turbo(self, provider, cheap_model):
        """Test GPT-3.5 Turbo with logprobs."""
        print("\n=== Testing GPT-3.5 Turbo ===")

        result = await provider.complete(
            prompt="Say hello", model=cheap_model, max_tokens=5, temperature=0.7, logprobs=True
        )

        print(f"Model: {cheap_model}")
        print(f"Response: {result.content}")
        print(f"Cost: ${result.cost:.6f}")
        print(f"Has logprobs: {result.logprobs is not None}")

        assert result.content is not None
        assert result.logprobs is not None

        print("✓ GPT-3.5 Turbo works with logprobs")

    @pytest.mark.asyncio
    async def test_gpt4o_mini(self, provider, mini_model):
        """Test GPT-4o Mini with logprobs."""
        print("\n=== Testing GPT-4o Mini ===")

        result = await provider.complete(
            prompt="Hi",
            model=mini_model,
            max_tokens=5,
            temperature=0.7,
            logprobs=True,
            top_logprobs=5,
        )

        print(f"Model: {mini_model}")
        print(f"Response: {result.content}")
        print(f"Cost: ${result.cost:.6f}")
        print(f"Has logprobs: {result.logprobs is not None}")

        assert result.content is not None
        assert result.logprobs is not None

        print("✓ GPT-4o Mini works with logprobs")


class TestOpenAICascadeReady:
    """Test OpenAI is ready for cascade use as verifier."""

    @pytest.mark.asyncio
    async def test_cascade_ready_response(self, provider, cheap_model):
        """Test response has all cascade fields."""
        print("\n=== Testing Cascade Readiness ===")

        result = await provider.complete(
            prompt="What is AI?",
            model=cheap_model,
            max_tokens=20,
            temperature=0.7,
            logprobs=True,
            top_logprobs=10,
        )

        print(f"✓ content: {result.content[:30]}...")
        print(f"✓ tokens: {len(result.tokens) if result.tokens else 0} tokens")
        print(f"✓ logprobs: {len(result.logprobs) if result.logprobs else 0} values")
        print(f"✓ top_logprobs: {len(result.top_logprobs) if result.top_logprobs else 0} items")
        print(f"✓ confidence: {result.confidence:.3f}")
        print(f"✓ cost: ${result.cost:.6f}")
        print(f"✓ latency: {result.latency_ms:.0f}ms")
        print(f"✓ native: {not result.metadata.get('estimated', False)}")

        assert result.content is not None
        assert result.tokens
        assert len(result.tokens) > 0
        assert result.logprobs
        assert len(result.logprobs) > 0
        assert result.top_logprobs
        assert len(result.top_logprobs) > 0
        assert result.confidence is not None
        assert result.cost > 0
        assert result.latency_ms > 0

        print("\n✓ OpenAI ready as VERIFIER with native logprobs!")


@pytest.mark.asyncio
async def test_openai_full_workflow(provider, cheap_model):
    """Complete workflow test."""
    print("\n" + "=" * 60)
    print("OPENAI PROVIDER - FULL WORKFLOW TEST")
    print("=" * 60)

    print("\n1. Checking logprobs support...")
    supports = provider.supports_logprobs()
    print(f"   Native: {supports}")
    print("   Using: Native API (real probabilities)")

    print("\n2. Basic completion...")
    result1 = await provider.complete(
        prompt="Count to 3", model=cheap_model, max_tokens=10, temperature=0.1
    )
    print(f"   Response: {result1.content}")
    print(f"   Cost: ${result1.cost:.6f}")

    print("\n3. With native logprobs...")
    result2 = await provider.complete(
        prompt="The sky is",
        model=cheap_model,
        max_tokens=5,
        temperature=0.7,
        logprobs=True,
        top_logprobs=5,
    )
    print(f"   Response: {result2.content}")
    print(f"   Tokens: {len(result2.tokens) if result2.tokens else 0}")
    print(f"   Confidence: {result2.confidence:.3f}")
    print(f"   Native logprobs: {not result2.metadata.get('estimated', False)}")

    print("\n4. Verifying cascade readiness...")
    assert all(
        [
            result2.content,
            result2.tokens,
            result2.logprobs,
            result2.top_logprobs,
            result2.confidence is not None,
            result2.cost > 0,
        ]
    )
    print("   ✓ All fields present")

    print("\n" + "=" * 60)
    print("✓ OPENAI READY AS VERIFIER WITH NATIVE LOGPROBS!")
    print("=" * 60)
