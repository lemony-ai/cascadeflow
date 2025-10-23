"""
Provider Investigation as Pytest Tests

Run with: pytest tests/test_provider_investigation.py -v -s
"""

import os
import statistics

import pytest
from cascadeflow.config import ModelConfig
from cascadeflow.speculative import WholeResponseCascade
from dotenv import load_dotenv

from cascadeflow.providers import PROVIDER_REGISTRY

# Load environment variables
load_dotenv()

# ==========================================
# TEST QUERIES
# ==========================================

TEST_QUERIES = {
    "trivial": [
        "What color is the sky?",
        "Is water wet?",
        "What is 2+2?",
    ],
    "simple": [
        "What is Python?",
        "Explain photosynthesis briefly",
        "What causes rain?",
    ],
    "moderate": [
        "How does blockchain technology work?",
        "Explain the difference between supervised and unsupervised learning",
        "What are the main causes of climate change?",
    ],
    "complex": [
        "Explain Gödel's incompleteness theorems",
        "Compare and contrast different political systems",
        "Analyze the philosophical implications of consciousness",
    ],
}

# ==========================================
# FIXTURES
# ==========================================


@pytest.fixture(scope="module")
def available_providers():
    """Get all available provider INSTANCES (not ModelConfigs!)."""
    providers = {}

    # CRITICAL: Return provider instances, keyed by provider name
    # Your speculative.py does: provider = self.providers[self.drafter.provider]
    # So if drafter.provider = 'anthropic', we need providers['anthropic'] to be an instance

    if os.getenv("ANTHROPIC_API_KEY"):
        providers["anthropic"] = PROVIDER_REGISTRY["anthropic"]()

    if os.getenv("OPENAI_API_KEY"):
        providers["openai"] = PROVIDER_REGISTRY["openai"]()

    if os.getenv("GROQ_API_KEY"):
        providers["groq"] = PROVIDER_REGISTRY["groq"]()

    if not providers:
        pytest.skip("No provider API keys found")

    return providers


@pytest.fixture(scope="module")
def model_configs():
    """Get ModelConfig objects for drafters and verifiers."""
    return {
        "haiku": ModelConfig(
            name="claude-3-5-haiku-20241022",
            provider="anthropic",  # Must match key in providers dict
            cost=0.00025,
            speed_ms=300,
            quality_score=0.75,
        ),
        "sonnet": ModelConfig(
            name="claude-sonnet-4",
            provider="anthropic",
            cost=0.003,
            speed_ms=1000,
            quality_score=0.92,
        ),
        "gpt35": ModelConfig(
            name="gpt-3.5-turbo",
            provider="openai",  # Must match key in providers dict
            cost=0.002,
            speed_ms=800,
            quality_score=0.70,
        ),
        "gpt4o": ModelConfig(
            name="gpt-4o", provider="openai", cost=0.005, speed_ms=2000, quality_score=0.95
        ),
        "groq": ModelConfig(
            name="llama-3.1-8b-instant",
            provider="groq",  # Must match key in providers dict
            cost=0.0,
            speed_ms=100,
            quality_score=0.70,
        ),
    }


@pytest.fixture(scope="module")
def verifier_model():
    """Get verifier model (GPT-4o)."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OpenAI API key required for verifier")

    return ModelConfig(
        name="gpt-4o", provider="openai", cost=0.005, speed_ms=2000, quality_score=0.95
    )


# ==========================================
# TEST 1: CONFIDENCE VARIANCE
# ==========================================


@pytest.mark.asyncio
async def test_confidence_variance_all_providers(
    available_providers, model_configs, verifier_model
):
    """Test confidence variance across all available providers."""

    print("\n" + "=" * 70)
    print("TEST 1: CONFIDENCE VARIANCE")
    print("=" * 70)

    test_query = "What is Python programming language?"
    num_runs = 10
    all_results = {}

    # Map provider names to their drafter ModelConfigs
    provider_to_drafter = {"anthropic": "haiku", "openai": "gpt35", "groq": "groq"}

    for provider_name in available_providers.keys():
        drafter_key = provider_to_drafter.get(provider_name)
        if not drafter_key or drafter_key not in model_configs:
            continue

        print(f"\nTesting {provider_name}...")

        cascade = WholeResponseCascade(
            drafter=model_configs[drafter_key],
            verifier=verifier_model,
            providers=available_providers,  # Provider instances!
        )

        confidences = []
        acceptances = []

        for i in range(num_runs):
            try:
                result = await cascade.execute(test_query, max_tokens=100)
                confidences.append(result.draft_confidence)
                acceptances.append(1 if result.draft_accepted else 0)
                print(
                    f"  Run {i+1}: confidence={result.draft_confidence:.3f}, accepted={result.draft_accepted}"
                )
            except Exception as e:
                print(f"  Run {i+1}: ERROR - {e}")

        if confidences:
            result_data = {
                "mean_confidence": statistics.mean(confidences),
                "stdev_confidence": statistics.stdev(confidences) if len(confidences) > 1 else 0,
                "min_confidence": min(confidences),
                "max_confidence": max(confidences),
                "acceptance_rate": statistics.mean(acceptances),
            }
            all_results[provider_name] = result_data

            print(f"\n  Results for {provider_name}:")
            print(f"    Mean confidence:   {result_data['mean_confidence']:.3f}")
            print(f"    Std deviation:     {result_data['stdev_confidence']:.3f}")
            print(
                f"    Range:             {result_data['min_confidence']:.3f} - {result_data['max_confidence']:.3f}"
            )
            print(f"    Acceptance rate:   {result_data['acceptance_rate']*100:.1f}%")

            if result_data["stdev_confidence"] > 0.05:
                print(f"    ⚠️  HIGH VARIANCE (>{0.05})")

    # Assertions
    assert len(all_results) > 0, "No providers completed successfully"

    # Store results for later tests
    pytest.variance_results = all_results


# ==========================================
# TEST 2: ACCEPTANCE BY COMPLEXITY
# ==========================================


@pytest.mark.asyncio
async def test_acceptance_by_complexity(available_providers, model_configs, verifier_model):
    """Test acceptance rates by query complexity for all providers."""

    print("\n" + "=" * 70)
    print("TEST 2: ACCEPTANCE BY COMPLEXITY")
    print("=" * 70)

    all_results = {}

    # Map provider names to their drafter ModelConfigs
    provider_to_drafter = {"anthropic": "haiku", "openai": "gpt35", "groq": "groq"}

    for provider_name in available_providers.keys():
        drafter_key = provider_to_drafter.get(provider_name)
        if not drafter_key or drafter_key not in model_configs:
            continue

        print(f"\n{provider_name.upper()}:")

        cascade = WholeResponseCascade(
            drafter=model_configs[drafter_key],
            verifier=verifier_model,
            providers=available_providers,  # Provider instances!
        )

        provider_results = {}

        for complexity, query_list in TEST_QUERIES.items():
            acceptances = []
            confidences = []

            print(f"\n  Testing {complexity} queries...")

            for query in query_list:
                try:
                    result = await cascade.execute(query, max_tokens=100)
                    acceptances.append(1 if result.draft_accepted else 0)
                    confidences.append(result.draft_confidence)
                    print(
                        f"    {query[:40]:40} conf={result.draft_confidence:.3f}, accepted={result.draft_accepted}"
                    )
                except Exception as e:
                    print(f"    {query[:40]:40} ERROR: {e}")

            if confidences:
                provider_results[complexity] = {
                    "acceptance_rate": statistics.mean(acceptances),
                    "mean_confidence": statistics.mean(confidences),
                    "stdev_confidence": (
                        statistics.stdev(confidences) if len(confidences) > 1 else 0
                    ),
                }

                print(
                    f"    → {complexity:10} acceptance: {provider_results[complexity]['acceptance_rate']*100:5.1f}%"
                )

        all_results[provider_name] = provider_results

    # Print summary
    print("\n" + "-" * 70)
    print("ACCEPTANCE SUMMARY")
    print("-" * 70)

    for provider_name, complexity_data in all_results.items():
        print(f"\n{provider_name.upper()}:")
        for complexity, data in complexity_data.items():
            print(
                f"  {complexity:10} {data['acceptance_rate']*100:5.1f}%  (conf: {data['mean_confidence']:.3f} ± {data['stdev_confidence']:.3f})"
            )

    # Store results for analysis
    pytest.acceptance_results = all_results

    # Assertions
    assert len(all_results) > 0, "No providers completed successfully"


# ==========================================
# TEST 3: CALCULATE ADJUSTMENTS
# ==========================================


def test_calculate_provider_adjustments():
    """Calculate recommended provider-specific threshold adjustments."""

    print("\n" + "=" * 70)
    print("TEST 3: RECOMMENDED ADJUSTMENTS")
    print("=" * 70)

    # Get results from previous tests
    if not hasattr(pytest, "acceptance_results"):
        pytest.skip("Acceptance test must run first")

    acceptance_results = pytest.acceptance_results

    # Use OpenAI as baseline
    baseline_acceptance = (
        acceptance_results.get("gpt35", {}).get("moderate", {}).get("acceptance_rate", 0.5)
    )

    adjustments = {}

    for provider_name, complexity_data in acceptance_results.items():
        moderate_data = complexity_data.get("moderate", {})
        provider_acceptance = moderate_data.get("acceptance_rate", 0.5)

        # Calculate adjustment
        if provider_acceptance > baseline_acceptance + 0.1:
            adjustment = 1.0 + ((provider_acceptance - baseline_acceptance) * 0.5)
        elif provider_acceptance < baseline_acceptance - 0.1:
            adjustment = 1.0 - ((baseline_acceptance - provider_acceptance) * 0.5)
        else:
            adjustment = 1.0

        adjustments[provider_name] = round(adjustment, 2)

    # Print recommendations
    print("\nProvider-specific threshold multipliers:")
    print("(Applied as: effective_threshold = base_threshold * multiplier)")
    print()

    for provider_name, multiplier in adjustments.items():
        interpretation = ""
        if multiplier > 1.05:
            interpretation = "⚠️  MORE SELECTIVE (raises threshold)"
        elif multiplier < 0.95:
            interpretation = "⚠️  LESS SELECTIVE (lowers threshold)"
        else:
            interpretation = "✓  NO ADJUSTMENT NEEDED"

        print(f"  '{provider_name}': {multiplier:.2f}  # {interpretation}")

    # Final recommendations
    print("\n" + "=" * 70)
    print("FINAL RECOMMENDATIONS")
    print("=" * 70)

    needs_adjustment = any(abs(mult - 1.0) > 0.05 for mult in adjustments.values())

    if needs_adjustment:
        print("\n✅ PROVIDER-SPECIFIC THRESHOLDS RECOMMENDED")
        print("\nAdd to quality.py:")
        print("\nPROVIDER_CONFIDENCE_ADJUSTMENTS = {")
        for provider_name, multiplier in adjustments.items():
            print(f"    '{provider_name}': {multiplier},")
        print("}")
    else:
        print("\n✅ NO PROVIDER-SPECIFIC ADJUSTMENTS NEEDED")

    # Check variance
    if hasattr(pytest, "variance_results"):
        high_variance = [
            name
            for name, data in pytest.variance_results.items()
            if data["stdev_confidence"] > 0.05
        ]

        if high_variance:
            print(f"\n⚠️  HIGH VARIANCE DETECTED: {', '.join(high_variance)}")
            print("Consider using confidence bands or reducing temperature")
        else:
            print("\n✅ LOW VARIANCE - Point thresholds are reliable")

    print("\n" + "=" * 70)

    # Store for potential use
    pytest.provider_adjustments = adjustments

    # Assertions
    assert adjustments, "Should calculate adjustments for at least one provider"
