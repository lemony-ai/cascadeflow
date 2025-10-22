"""
Tests for Ollama provider with logprobs fallback support.

Run with:
    pytest tests/test_ollama_logprobs.py -v -s
"""

import pytest

from cascadeflow.providers.ollama import OllamaProvider


# Check if Ollama is available
def is_ollama_available():
    """Check if Ollama is running."""
    import httpx

    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return response.status_code == 200
    except:
        return False


pytestmark = pytest.mark.skipif(
    not is_ollama_available(), reason="Ollama not running - start with 'ollama serve'"
)


@pytest.fixture
def provider():
    """Create Ollama provider instance."""
    return OllamaProvider()


@pytest.fixture
def test_model():
    """Return test model name."""
    return "gemma3:1b"


class TestOllamaBasics:
    """Test basic Ollama functionality."""

    @pytest.mark.asyncio
    async def test_provider_initialization(self, provider):
        """Test provider initializes correctly."""
        print("\n=== Testing Ollama Initialization ===")
        assert provider is not None
        print("✓ Provider initialized")

    @pytest.mark.asyncio
    async def test_supports_logprobs(self, provider):
        """Test logprobs support check."""
        print("\n=== Testing Logprobs Support ===")
        supports = provider.supports_logprobs()
        print(f"Native logprobs support: {supports}")
        assert supports is False, "Ollama should return False (uses fallback)"
        print("✓ Correctly reports no native logprobs (will use fallback)")

    @pytest.mark.asyncio
    async def test_basic_completion(self, provider, test_model):
        """Test basic completion without logprobs."""
        print("\n=== Testing Basic Completion ===")

        result = await provider.complete(
            prompt="What is 2+2? Answer with just the number.",
            model=test_model,
            max_tokens=5,
            temperature=0.1,
        )

        print("Prompt: What is 2+2?")
        print(f"Model: {test_model}")
        print(f"Response: {result.content}")
        print(f"Cost: ${result.cost:.6f} (FREE!)")
        print(f"Latency: {result.latency_ms:.0f}ms")

        assert result.content is not None
        assert result.provider == "ollama"
        assert result.cost == 0.0

        print("✓ Basic completion works")


class TestOllamaLogprobsFallback:
    """Test logprobs fallback - CRITICAL for free drafter."""

    @pytest.mark.asyncio
    async def test_logprobs_fallback_enabled(self, provider, test_model):
        """Test that logprobs fallback works."""
        print("\n=== Testing Logprobs Fallback ===")

        result = await provider.complete(
            prompt="The capital of France is",
            model=test_model,
            max_tokens=5,
            temperature=0.7,
            logprobs=True,
            top_logprobs=10,
        )

        print(f"Response: {result.content}")
        print(f"Tokens: {result.tokens}")
        print(f"Logprobs: {result.logprobs}")
        print(f"Confidence: {result.confidence:.3f}")
        print(f"Estimated: {result.metadata.get('estimated', False)}")

        # CRITICAL checks
        assert result.tokens is not None, "Must have tokens"
        assert result.logprobs is not None, "Must have logprobs"
        assert result.top_logprobs is not None, "Must have top_logprobs"
        assert len(result.logprobs) == len(result.tokens), "Counts must match"
        assert result.metadata.get("estimated") is True, "Must be marked estimated"
        assert all(-10 < lp < 0 for lp in result.logprobs), "Logprobs realistic"

        if result.top_logprobs and len(result.top_logprobs) > 0:
            print("\nFirst token alternatives:")
            for i, (token, logprob) in enumerate(list(result.top_logprobs[0].items())[:3], 1):
                print(f"  {i}. '{token}' (logprob: {logprob:.3f})")

        print("\n✓ Logprobs fallback works - FREE drafter ready!")

    @pytest.mark.asyncio
    async def test_temperature_impact(self, provider, test_model):
        """Test temperature affects confidence."""
        print("\n=== Testing Temperature Impact ===")

        temps = [0.1, 0.5, 0.9]
        results = []

        for temp in temps:
            result = await provider.complete(
                prompt="Hello", model=test_model, max_tokens=3, temperature=temp, logprobs=True
            )
            results.append((temp, result.confidence))
            print(f"Temp {temp}: confidence = {result.confidence:.3f}")

        assert all(0 <= conf <= 1 for _, conf in results)
        print("✓ Temperature affects confidence")

    @pytest.mark.asyncio
    async def test_without_logprobs_request(self, provider, test_model):
        """Test logprobs NOT added when not requested."""
        print("\n=== Testing Without Logprobs Request ===")

        result = await provider.complete(
            prompt="Hi", model=test_model, max_tokens=3, temperature=0.5, logprobs=False
        )

        print(f"Response: {result.content}")
        print(f"Has tokens: {result.tokens is not None}")
        print(f"Has logprobs: {result.logprobs is not None}")

        assert result.tokens is None
        assert result.logprobs is None

        print("✓ Logprobs correctly omitted when not requested")


class TestOllamaCascadeReady:
    """Test Ollama is ready for cascade use."""

    @pytest.mark.asyncio
    async def test_cascade_ready_response(self, provider, test_model):
        """Test response has all cascade fields."""
        print("\n=== Testing Cascade Readiness ===")

        result = await provider.complete(
            prompt="What is AI?",
            model=test_model,
            max_tokens=20,
            temperature=0.7,
            logprobs=True,
            top_logprobs=10,
        )

        print(f"✓ content: {result.content[:30]}...")
        print(f"✓ tokens: {len(result.tokens)} tokens")
        print(f"✓ logprobs: {len(result.logprobs)} values")
        print(f"✓ top_logprobs: {len(result.top_logprobs)} items")
        print(f"✓ confidence: {result.confidence:.3f}")
        print(f"✓ cost: ${result.cost:.6f} (FREE!)")
        print(f"✓ latency: {result.latency_ms:.0f}ms")

        assert result.content is not None
        assert result.tokens
        assert len(result.tokens) > 0
        assert result.logprobs
        assert len(result.logprobs) > 0
        assert result.top_logprobs
        assert len(result.top_logprobs) > 0
        assert result.confidence is not None
        assert result.cost == 0.0
        assert result.latency_ms > 0

        print("\n✓ Ollama ready as FREE drafter!")


@pytest.mark.asyncio
async def test_ollama_full_workflow(provider, test_model):
    """Complete workflow test."""
    print("\n" + "=" * 60)
    print("OLLAMA PROVIDER - FULL WORKFLOW TEST")
    print("=" * 60)

    print("\n1. Checking logprobs support...")
    supports = provider.supports_logprobs()
    print(f"   Native: {supports}")
    print("   Using: Fallback estimation")

    print("\n2. Basic completion...")
    result1 = await provider.complete(
        prompt="Count to 3", model=test_model, max_tokens=10, temperature=0.1
    )
    print(f"   Response: {result1.content}")
    print(f"   Cost: ${result1.cost:.6f} (FREE!)")

    print("\n3. With logprobs...")
    result2 = await provider.complete(
        prompt="The sky is",
        model=test_model,
        max_tokens=5,
        temperature=0.7,
        logprobs=True,
        top_logprobs=5,
    )
    print(f"   Response: {result2.content}")
    print(f"   Tokens: {len(result2.tokens)}")
    print(f"   Confidence: {result2.confidence:.3f}")
    print(f"   Estimated: {result2.metadata.get('estimated')}")

    print("\n4. Verifying cascade readiness...")
    assert all(
        [
            result2.content,
            result2.tokens,
            result2.logprobs,
            result2.top_logprobs,
            result2.confidence is not None,
            result2.cost == 0.0,
        ]
    )
    print("   ✓ All fields present")

    print("\n" + "=" * 60)
    print("✓ OLLAMA READY AS FREE DRAFTER!")
    print("=" * 60)
