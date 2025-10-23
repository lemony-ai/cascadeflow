# Save as tests/test_confidence_integration.py
"""
Diagnostic tests for production confidence system integration.

Run with: pytest tests/test_confidence_integration.py -v -s
"""

import os

import pytest
from cascadeflow.config import ModelConfig
from cascadeflow.speculative import WholeResponseCascade
from dotenv import load_dotenv

from cascadeflow.providers import PROVIDER_REGISTRY

# Load environment variables
load_dotenv()


@pytest.fixture(scope="module")
def available_providers():
    """Get all available provider INSTANCES."""
    providers = {}

    if os.getenv("ANTHROPIC_API_KEY"):
        providers["anthropic"] = PROVIDER_REGISTRY["anthropic"]()

    if os.getenv("OPENAI_API_KEY"):
        providers["openai"] = PROVIDER_REGISTRY["openai"]()

    if os.getenv("GROQ_API_KEY"):
        providers["groq"] = PROVIDER_REGISTRY["groq"]()

    if not providers:
        pytest.skip("No provider API keys found")

    return providers


@pytest.mark.asyncio
async def test_confidence_estimator_initialization(available_providers):
    """Test that all providers initialize the confidence estimator."""

    for provider_name, provider in available_providers.items():
        print(f"\n{'='*60}")
        print(f"Testing {provider_name.upper()} Provider")
        print("=" * 60)

        # Check estimator exists
        has_estimator = hasattr(provider, "_confidence_estimator")
        print(f"  Has _confidence_estimator: {has_estimator}")

        if has_estimator:
            is_none = provider._confidence_estimator is None
            print(f"  Estimator is None: {is_none}")

            if not is_none:
                print(f"  Estimator type: {type(provider._confidence_estimator).__name__}")
                print(f"  Estimator provider: {provider._confidence_estimator.provider}")
            else:
                print("  ❌ PROBLEM: Estimator is None - import failed")
        else:
            print("  ❌ PROBLEM: Estimator attribute missing")

        assert has_estimator, f"{provider_name} missing _confidence_estimator"
        assert provider._confidence_estimator is not None, f"{provider_name} estimator is None"


@pytest.mark.asyncio
async def test_direct_provider_confidence(available_providers):
    """Test confidence calculation directly through provider."""

    test_query = "What is Python programming language?"

    models = {
        "openai": "gpt-3.5-turbo",
        "anthropic": "claude-3-5-haiku-20241022",
        "groq": "llama-3.1-8b-instant",
    }

    for provider_name, provider in available_providers.items():
        print(f"\n{'='*70}")
        print(f"TESTING {provider_name.upper()} DIRECT")
        print("=" * 70)

        # Monkey patch to trace confidence calculation
        original_calc = provider.calculate_confidence
        calc_calls = []

        def traced_calc(response, metadata=None):
            print("\n  calculate_confidence called:")
            print(f"     Response length: {len(response)}")
            print(f"     Metadata: {metadata}")
            result = original_calc(response, metadata)
            calc_calls.append({"metadata": metadata, "result": result})
            print(f"     → Returned: {result}")
            return result

        provider.calculate_confidence = traced_calc

        # Make API call
        result = await provider.complete(
            prompt=test_query,
            model=models[provider_name],
            max_tokens=100,
            temperature=0.7,
            logprobs=True,  # Request logprobs
            top_logprobs=5,
        )

        print("\n  Final result:")
        print(f"     Content: {result.content[:100]}...")
        print(f"     Confidence: {result.confidence}")
        print(f"     Has logprobs: {result.logprobs is not None}")
        print(f"     Calc calls: {len(calc_calls)}")

        # Verify confidence was calculated
        assert len(calc_calls) > 0, f"{provider_name}: calculate_confidence was never called"
        assert result.confidence > 0.0, f"{provider_name}: Confidence is 0.0"

        # Restore original method
        provider.calculate_confidence = original_calc


@pytest.mark.asyncio
async def test_cascade_confidence_trace(available_providers):
    """Test confidence calculation through cascade (mimics original test)."""

    print(f"\n{'='*70}")
    print("TESTING CASCADE CONFIDENCE")
    print("=" * 70)

    # Use same setup as original test
    verifier_model = ModelConfig(
        name="gpt-4o", provider="openai", cost=0.005, speed_ms=2000, quality_score=0.95
    )

    drafter_configs = {
        "anthropic": ModelConfig(
            name="claude-3-5-haiku-20241022",
            provider="anthropic",
            cost=0.00025,
            speed_ms=300,
            quality_score=0.75,
        ),
        "openai": ModelConfig(
            name="gpt-3.5-turbo", provider="openai", cost=0.002, speed_ms=800, quality_score=0.70
        ),
        "groq": ModelConfig(
            name="llama-3.1-8b-instant", provider="groq", cost=0.0, speed_ms=100, quality_score=0.70
        ),
    }

    test_query = "What is Python programming language?"

    for provider_name, drafter in drafter_configs.items():
        if provider_name not in available_providers:
            continue

        print(f"\n  Testing cascade with {provider_name} drafter:")

        # Trace the drafter provider's confidence calculation
        provider = available_providers[provider_name]
        original_calc = provider.calculate_confidence
        calc_calls = []

        def traced_calc(response, metadata=None):
            call_info = {
                "response_len": len(response),
                "metadata": metadata,
            }
            result = original_calc(response, metadata)
            call_info["result"] = result
            calc_calls.append(call_info)
            print("     Drafter confidence calculation:")
            print(f"       Response: {len(response)} chars")
            print(f"       Metadata keys: {list(metadata.keys()) if metadata else 'None'}")
            print(f"       → Confidence: {result}")
            return result

        provider.calculate_confidence = traced_calc

        # Create cascade
        cascade = WholeResponseCascade(
            drafter=drafter, verifier=verifier_model, providers=available_providers
        )

        # Execute (this is what original test does)
        result = await cascade.execute(test_query, max_tokens=100)

        print(f"     Draft confidence: {result.draft_confidence}")
        print(f"     Draft accepted: {result.draft_accepted}")
        print(f"     Calc calls: {len(calc_calls)}")

        if calc_calls:
            last_call = calc_calls[-1]
            print(f"     Last calc metadata: {last_call['metadata']}")

        # This mimics the problem from original test
        if result.draft_confidence == 0.0:
            print("     ❌ PROBLEM: Draft confidence is 0.0!")
            if calc_calls:
                print(f"     Debug info: {calc_calls[-1]}")

        # Restore
        provider.calculate_confidence = original_calc


@pytest.mark.asyncio
async def test_estimator_direct_call():
    """Test the confidence estimator directly to isolate issues."""

    print(f"\n{'='*70}")
    print("TESTING ESTIMATOR DIRECTLY")
    print("=" * 70)

    from cascadeflow.quality.confidence import ProductionConfidenceEstimator

    # Test with semantic only (no logprobs)
    estimator = ProductionConfidenceEstimator("anthropic")

    response = (
        "Python is a high-level programming language known for its readability and versatility."
    )

    analysis = estimator.estimate(
        response=response, query="What is Python?", temperature=0.7, finish_reason="end_turn"
    )

    print("\n  Semantic-only test (Anthropic-style):")
    print(f"     Final confidence: {analysis.final_confidence}")
    print(f"     Method: {analysis.method_used}")
    print(f"     Semantic: {analysis.semantic_confidence}")
    print(f"     Calibrated: {analysis.calibrated_confidence}")

    assert analysis.final_confidence > 0.0, "Direct estimator call returned 0.0!"

    # Test with logprobs (OpenAI-style)
    estimator2 = ProductionConfidenceEstimator("openai")

    # Simulate high confidence logprobs
    logprobs = [-0.1, -0.05, -0.08, -0.12, -0.09]
    tokens = ["Python", " is", " a", " programming", " language"]

    analysis2 = estimator2.estimate(
        response=response,
        query="What is Python?",
        logprobs=logprobs,
        tokens=tokens,
        temperature=0.7,
        finish_reason="stop",
    )

    print("\n  Hybrid test (OpenAI-style with logprobs):")
    print(f"     Final confidence: {analysis2.final_confidence}")
    print(f"     Method: {analysis2.method_used}")
    print(f"     Logprobs: {analysis2.logprobs_confidence}")
    print(f"     Semantic: {analysis2.semantic_confidence}")

    assert analysis2.final_confidence > 0.0, "Hybrid estimator call returned 0.0!"
    assert analysis2.method_used == "hybrid", "Should use hybrid method with logprobs"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
