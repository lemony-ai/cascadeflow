# Save as tests/test_confidence_integration.py
"""
Diagnostic tests for production confidence system integration.

Run with: pytest tests/test_confidence_integration.py -v -s
"""

import pytest
import asyncio
from cascadeflow.providers import PROVIDER_REGISTRY
from unittest.mock import patch


@pytest.mark.asyncio
async def test_confidence_estimator_initialization():
    """Test that all providers initialize the confidence estimator."""

    providers_to_test = ['openai', 'anthropic', 'groq']

    for provider_name in providers_to_test:
        print(f"\n{'='*60}")
        print(f"Testing {provider_name.upper()} Provider")
        print('='*60)

        try:
            provider = PROVIDER_REGISTRY[provider_name]()

            # Check estimator exists
            has_estimator = hasattr(provider, '_confidence_estimator')
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

        except Exception as e:
            print(f"  ❌ ERROR initializing: {type(e).__name__}: {e}")
            pytest.fail(f"Failed to initialize {provider_name}: {e}")


@pytest.mark.asyncio
async def test_confidence_calculation_trace():
    """Trace confidence calculation to see what's happening."""

    # Test with Anthropic first (returns 0.0 in your tests)
    print("\n" + "="*70)
    print("TRACING ANTHROPIC CONFIDENCE CALCULATION")
    print("="*70)

    provider = PROVIDER_REGISTRY['anthropic']()

    # Wrap the estimate method to trace calls
    if provider._confidence_estimator:
        original_estimate = provider._confidence_estimator.estimate
        calls = []

        def traced_estimate(*args, **kwargs):
            call_info = {
                'args': args,
                'kwargs': kwargs,
                'response_length': len(kwargs.get('response', args[0] if args else '')),
                'has_logprobs': kwargs.get('logprobs') is not None,
                'has_query': kwargs.get('query') is not None,
                'temperature': kwargs.get('temperature'),
                'finish_reason': kwargs.get('finish_reason'),
            }
            calls.append(call_info)

            print(f"\n  → estimate() called:")
            print(f"     Response length: {call_info['response_length']}")
            print(f"     Has logprobs: {call_info['has_logprobs']}")
            print(f"     Has query: {call_info['has_query']}")
            print(f"     Temperature: {call_info['temperature']}")
            print(f"     Finish reason: {call_info['finish_reason']}")

            result = original_estimate(*args, **kwargs)

            print(f"\n  → estimate() returned:")
            print(f"     Final confidence: {result.final_confidence}")
            print(f"     Method used: {result.method_used}")
            print(f"     Semantic confidence: {result.semantic_confidence}")
            print(f"     Logprobs confidence: {result.logprobs_confidence}")

            return result

        provider._confidence_estimator.estimate = traced_estimate

    # Make a test call
    try:
        result = await provider.complete(
            prompt="What is 2+2?",
            model="claude-3-5-haiku-20241022",
            max_tokens=10,
            temperature=0.7
        )

        print(f"\n  Final ModelResponse:")
        print(f"     Content: {result.content}")
        print(f"     Confidence: {result.confidence}")
        print(f"     Metadata: {result.metadata}")

        # Verify estimate was called
        assert len(calls) > 0, "estimate() was never called!"
        assert result.confidence > 0.0, "Confidence is 0.0 - something is wrong"

    except Exception as e:
        print(f"\n  ❌ ERROR during completion: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Completion failed: {e}")


@pytest.mark.asyncio
async def test_openai_logprobs_usage():
    """Test that OpenAI uses logprobs when requested."""

    print("\n" + "="*70)
    print("TESTING OPENAI LOGPROBS INTEGRATION")
    print("="*70)

    provider = PROVIDER_REGISTRY['openai']()

    # Track what metadata is passed to calculate_confidence
    original_calc = provider.calculate_confidence
    metadata_received = []

    def traced_calc(response, metadata=None):
        metadata_received.append(metadata)
        print(f"\n  calculate_confidence called with:")
        print(f"     Response length: {len(response)}")
        print(f"     Metadata keys: {metadata.keys() if metadata else 'None'}")
        if metadata:
            print(f"     Has logprobs: {'logprobs' in metadata}")
            print(f"     Has tokens: {'tokens' in metadata}")
            if 'logprobs' in metadata:
                print(f"     Logprobs count: {len(metadata['logprobs'])}")
        return original_calc(response, metadata)

    provider.calculate_confidence = traced_calc

    # Test WITH logprobs
    print("\n  Testing WITH logprobs=True:")
    result = await provider.complete(
        prompt="What is 2+2?",
        model="gpt-3.5-turbo",
        max_tokens=10,
        temperature=0.7,
        logprobs=True,
        top_logprobs=5
    )

    print(f"\n  Result:")
    print(f"     Confidence: {result.confidence}")
    print(f"     Has logprobs in response: {result.logprobs is not None}")