"""
Comprehensive Diagnostic Integration Test Suite

Tests the integration between agent.py and speculative.py,
validating that all diagnostic data flows correctly.

Features:
- Auto-detects available providers
- Works with any provider combination
- Mock mode for offline testing
- Validates all diagnostic fields
- Performance analysis
- Quality system validation
"""

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cascadeflow.config import ModelConfig

from cascadeflow.agent import CascadeAgent, CascadeResult
from cascadeflow.quality import QualityConfig

# ============================================================================
# MOCK PROVIDER FOR OFFLINE TESTING
# ============================================================================


class MockProvider:
    """Mock provider for testing without API keys."""

    def __init__(self):
        self.call_count = 0

    async def complete(
        self, model: str, prompt: str, max_tokens: int = 100, temperature: float = 0.7, **kwargs
    ) -> dict[str, Any]:
        """Mock completion."""
        self.call_count += 1

        # Simulate different responses based on model
        if "draft" in model or "small" in model or "fast" in model:
            # Draft model - lower confidence
            content = f"Mock draft response to: {prompt[:30]}..."
            confidence = 0.75
            tokens = 50
        else:
            # Verifier model - higher confidence
            content = f"Mock verifier response to: {prompt[:30]}..."
            confidence = 0.92
            tokens = 60

        # Simulate response format
        class MockResponse:
            def __init__(self, content, confidence, tokens):
                self.content = content
                self.confidence = confidence
                self.tokens_used = tokens
                self.logprobs = None
                self.metadata = {"confidence_method": "mock"}

            def to_dict(self):
                return {
                    "content": self.content,
                    "confidence": self.confidence,
                    "tokens_used": self.tokens_used,
                    "logprobs": self.logprobs,
                    "metadata": self.metadata,
                    "confidence_method": "mock",
                }

        return MockResponse(content, confidence, tokens)


# ============================================================================
# PROVIDER DETECTION
# ============================================================================


def get_available_providers() -> dict[str, list[str]]:
    """
    Detect which providers have API keys configured.

    Returns:
        Dict mapping provider name to list of available models
    """
    available = {}

    # Check OpenAI
    if os.getenv("OPENAI_API_KEY"):
        available["openai"] = ["gpt-3.5-turbo", "gpt-4"]
        print("✓ OpenAI available")

    # Check Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        available["anthropic"] = ["claude-3-haiku-20240307", "claude-3-5-sonnet-20241022"]
        print("✓ Anthropic available")

    # Check Groq
    if os.getenv("GROQ_API_KEY"):
        available["groq"] = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]
        print("✓ Groq available")

    # Check Together
    if os.getenv("TOGETHER_API_KEY"):
        available["together"] = [
            "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        ]
        print("✓ Together available")

    # Check Ollama (local, no API key needed)
    try:
        import requests

        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = [m["name"] for m in response.json().get("models", [])]
            if models:
                available["ollama"] = models[:2]  # Use first 2 models
                print(f"✓ Ollama available ({len(models)} models)")
    except:
        pass

    return available


def create_mock_models() -> list[ModelConfig]:
    """Create mock model configs for testing without API keys."""
    return [
        ModelConfig(
            name="mock-draft", provider="mock", cost=0.0001, speed_ms=200, quality_score=0.7
        ),
        ModelConfig(
            name="mock-verifier", provider="mock", cost=0.001, speed_ms=500, quality_score=0.95
        ),
    ]


def create_models_from_providers(providers: dict[str, list[str]]) -> list[ModelConfig]:
    """Create model configs from available providers."""
    models = []

    if "groq" in providers:
        models.append(
            ModelConfig(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost=0.0,
                speed_ms=300,
                quality_score=0.75,
            )
        )
        if len(providers["groq"]) > 1:
            models.append(
                ModelConfig(
                    name="llama-3.3-70b-versatile",
                    provider="groq",
                    cost=0.0,
                    speed_ms=800,
                    quality_score=0.92,
                )
            )

    if "openai" in providers:
        if not models:
            models.append(
                ModelConfig(
                    name="gpt-3.5-turbo",
                    provider="openai",
                    cost=0.002,
                    speed_ms=800,
                    quality_score=0.85,
                )
            )
        models.append(
            ModelConfig(
                name="gpt-4", provider="openai", cost=0.03, speed_ms=2500, quality_score=0.95
            )
        )

    if "anthropic" in providers and not models:
        models.append(
            ModelConfig(
                name="claude-3-haiku-20240307",
                provider="anthropic",
                cost=0.00125,
                speed_ms=700,
                quality_score=0.85,
            )
        )
        if len(providers["anthropic"]) > 1:
            models.append(
                ModelConfig(
                    name="claude-3-5-sonnet-20241022",
                    provider="anthropic",
                    cost=0.003,
                    speed_ms=1500,
                    quality_score=0.96,
                )
            )

    if "ollama" in providers and not models:
        ollama_models = providers["ollama"]
        models.append(
            ModelConfig(
                name=ollama_models[0], provider="ollama", cost=0.0, speed_ms=400, quality_score=0.70
            )
        )
        if len(ollama_models) > 1:
            models.append(
                ModelConfig(
                    name=ollama_models[1],
                    provider="ollama",
                    cost=0.0,
                    speed_ms=600,
                    quality_score=0.85,
                )
            )

    return models


# ============================================================================
# DIAGNOSTIC VALIDATION
# ============================================================================


@dataclass
class DiagnosticCheck:
    """Result of a diagnostic field check."""

    field: str
    present: bool
    value: Any
    expected_type: type
    type_correct: bool


def validate_diagnostic_fields(result: CascadeResult) -> dict[str, DiagnosticCheck]:
    """
    Validate that all diagnostic fields are present and correct.

    Returns:
        Dict of field name to DiagnosticCheck
    """
    checks = {}

    # Core fields
    checks["content"] = DiagnosticCheck(
        "content", result.content is not None, result.content, str, isinstance(result.content, str)
    )
    checks["model_used"] = DiagnosticCheck(
        "model_used",
        result.model_used is not None,
        result.model_used,
        str,
        isinstance(result.model_used, str),
    )
    checks["total_cost"] = DiagnosticCheck(
        "total_cost",
        result.total_cost is not None,
        result.total_cost,
        float,
        isinstance(result.total_cost, (int, float)),
    )
    checks["latency_ms"] = DiagnosticCheck(
        "latency_ms",
        result.latency_ms is not None,
        result.latency_ms,
        float,
        isinstance(result.latency_ms, (int, float)),
    )

    # Quality system diagnostics
    checks["quality_score"] = DiagnosticCheck(
        "quality_score",
        result.quality_score is not None,
        result.quality_score,
        float,
        (
            isinstance(result.quality_score, (int, float))
            if result.quality_score is not None
            else True
        ),
    )
    checks["quality_threshold"] = DiagnosticCheck(
        "quality_threshold",
        result.quality_threshold is not None,
        result.quality_threshold,
        float,
        (
            isinstance(result.quality_threshold, (int, float))
            if result.quality_threshold is not None
            else True
        ),
    )

    # Timing breakdown
    checks["complexity_detection_ms"] = DiagnosticCheck(
        "complexity_detection_ms",
        result.complexity_detection_ms is not None,
        result.complexity_detection_ms,
        float,
        (
            isinstance(result.complexity_detection_ms, (int, float))
            if result.complexity_detection_ms is not None
            else True
        ),
    )
    checks["draft_generation_ms"] = DiagnosticCheck(
        "draft_generation_ms",
        result.draft_generation_ms is not None,
        result.draft_generation_ms,
        float,
        (
            isinstance(result.draft_generation_ms, (int, float))
            if result.draft_generation_ms is not None
            else True
        ),
    )
    checks["quality_verification_ms"] = DiagnosticCheck(
        "quality_verification_ms",
        result.quality_verification_ms is not None,
        result.quality_verification_ms,
        float,
        (
            isinstance(result.quality_verification_ms, (int, float))
            if result.quality_verification_ms is not None
            else True
        ),
    )

    # Response tracking
    checks["response_length"] = DiagnosticCheck(
        "response_length",
        result.response_length is not None,
        result.response_length,
        int,
        isinstance(result.response_length, int) if result.response_length is not None else True,
    )
    checks["response_word_count"] = DiagnosticCheck(
        "response_word_count",
        result.response_word_count is not None,
        result.response_word_count,
        int,
        (
            isinstance(result.response_word_count, int)
            if result.response_word_count is not None
            else True
        ),
    )

    # Cascade-specific
    if result.cascaded:
        checks["draft_cost"] = DiagnosticCheck(
            "draft_cost",
            result.draft_cost is not None,
            result.draft_cost,
            float,
            isinstance(result.draft_cost, (int, float)) if result.draft_cost is not None else True,
        )
        checks["cascade_overhead_ms"] = DiagnosticCheck(
            "cascade_overhead_ms",
            result.cascade_overhead_ms is not None,
            result.cascade_overhead_ms,
            float,
            (
                isinstance(result.cascade_overhead_ms, (int, float))
                if result.cascade_overhead_ms is not None
                else True
            ),
        )

    return checks


# ============================================================================
# TEST FUNCTIONS
# ============================================================================


async def test_with_real_providers(models: list[ModelConfig]) -> bool:
    """Test with real API providers."""
    print("\n" + "=" * 80)
    print("TEST: Real Provider Integration")
    print("=" * 80)

    try:
        agent = CascadeAgent(
            models=models, quality_config=QualityConfig.for_cascade(), verbose=True
        )

        print(f"\nInitialized agent with {len(models)} models")
        print(f"Drafter: {models[0].name}")
        print(f"Verifier: {models[-1].name}")

        # Test query
        query = "What is the capital of France?"
        print(f"\nQuery: {query}")
        print("-" * 80)

        result = await agent.run(query)

        # Validate diagnostics
        print("\n" + "=" * 80)
        print("DIAGNOSTIC VALIDATION")
        print("=" * 80)

        checks = validate_diagnostic_fields(result)

        passed = 0
        failed = 0

        for field, check in checks.items():
            if check.present and check.type_correct:
                print(f"  ✓ {field:30s}: {check.value}")
                passed += 1
            else:
                print(f"  ✗ {field:30s}: {'MISSING' if not check.present else 'WRONG TYPE'}")
                failed += 1

        print(f"\nResults: {passed} passed, {failed} failed")

        # Print sample diagnostics
        if passed > 0:
            print("\n" + "=" * 80)
            print("SAMPLE DIAGNOSTIC VALUES")
            print("=" * 80)
            if result.quality_score:
                print(f"Quality Score:        {result.quality_score:.3f}")
            if result.quality_threshold:
                print(f"Quality Threshold:    {result.quality_threshold:.3f}")
            print(f"Draft Accepted:       {result.draft_accepted}")
            if result.draft_generation_ms:
                print(f"Draft Latency:        {result.draft_generation_ms:.1f}ms")
            if result.quality_verification_ms:
                print(f"Quality Check:        {result.quality_verification_ms:.1f}ms")
            if result.cascade_overhead_ms:
                print(f"Cascade Overhead:     {result.cascade_overhead_ms:.1f}ms")
            print(f"Total Latency:        {result.latency_ms:.1f}ms")
            print(f"Total Cost:           ${result.total_cost:.6f}")

        # Print stats
        print("\n" + "=" * 80)
        print("AGENT STATISTICS")
        print("=" * 80)
        agent.print_stats()

        return failed == 0

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_with_mock_provider() -> bool:
    """Test with mock provider (no API keys needed)."""
    print("\n" + "=" * 80)
    print("TEST: Mock Provider (Offline)")
    print("=" * 80)

    try:
        # Create mock models
        models = create_mock_models()

        # Create agent with mock provider
        from cascadeflow.agent import CascadeAgent
        from cascadeflow.providers import PROVIDER_REGISTRY

        # Register mock provider
        PROVIDER_REGISTRY["mock"] = MockProvider

        agent = CascadeAgent(
            models=models, quality_config=QualityConfig.for_cascade(), verbose=True
        )

        print("\nInitialized agent with mock provider")
        print(f"Drafter: {models[0].name}")
        print(f"Verifier: {models[-1].name}")

        # Test queries
        test_queries = [
            "What is the capital of France?",
            "Explain quantum computing",
            "What is 2+2?",
        ]

        all_passed = True

        for i, query in enumerate(test_queries, 1):
            print(f"\n[Query {i}/{len(test_queries)}] {query}")
            print("-" * 80)

            result = await agent.run(query)

            # Basic validation
            checks = validate_diagnostic_fields(result)
            passed = sum(1 for c in checks.values() if c.present and c.type_correct)
            total = len(checks)

            print(f"✓ Diagnostics: {passed}/{total} fields valid")

            if passed < total:
                all_passed = False

        # Print final stats
        print("\n" + "=" * 80)
        print("AGENT STATISTICS (Mock Mode)")
        print("=" * 80)
        agent.print_stats()

        return all_passed

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_quality_system_validation() -> bool:
    """Test that quality system is working correctly."""
    print("\n" + "=" * 80)
    print("TEST: Quality System Validation")
    print("=" * 80)

    # This test requires real providers
    providers = get_available_providers()

    if not providers:
        print("⚠️  Skipping - requires real providers with API keys")
        return True  # Not a failure, just skipped

    models = create_models_from_providers(providers)

    if len(models) < 2:
        print("⚠️  Skipping - requires 2+ models")
        return True

    try:
        agent = CascadeAgent(
            models=models,
            quality_config=QualityConfig.for_cascade(),
            verbose=False,  # Less verbose for batch testing
        )

        # Run multiple queries
        test_queries = [
            "What is 2+2?",  # Trivial
            "What is the capital of France?",  # Simple
            "Explain how neural networks work",  # Moderate
        ]

        results = []
        print(f"\nRunning {len(test_queries)} test queries...")

        for query in test_queries:
            result = await agent.run(query)
            results.append(result)
            print(f"  ✓ {query[:40]:40s} | Draft: {result.draft_accepted}")

        # Analyze results
        print("\n" + "-" * 80)
        print("QUALITY SYSTEM ANALYSIS")
        print("-" * 80)

        # Check 1: Quality scores are being captured
        scores = [r.quality_score for r in results if r.quality_score is not None]
        print("\n1. Quality Score Capture")
        print(f"   Captured: {len(scores)}/{len(results)} ({len(scores)/len(results)*100:.1f}%)")

        if len(scores) == 0:
            print("   ✗ ISSUE: No quality scores captured!")
            return False

        # Check 2: Acceptance rate is reasonable
        acceptances = sum(1 for r in results if r.draft_accepted)
        acceptance_rate = acceptances / len(results) * 100
        print("\n2. Acceptance Rate")
        print(f"   Rate: {acceptance_rate:.1f}% ({acceptances}/{len(results)})")

        if acceptance_rate < 20 or acceptance_rate > 90:
            print("   ⚠️  WARNING: Acceptance rate outside expected range (30-70%)")

        # Check 3: Timing data is present
        timing_fields = [
            "draft_generation_ms",
            "quality_verification_ms",
            "complexity_detection_ms",
        ]
        timing_captured = sum(
            1 for r in results for field in timing_fields if getattr(r, field, None) is not None
        )
        timing_total = len(results) * len(timing_fields)
        print("\n3. Timing Data Capture")
        print(
            f"   Captured: {timing_captured}/{timing_total} ({timing_captured/timing_total*100:.1f}%)"
        )

        return True

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================


async def main():
    """Run all diagnostic tests."""
    print("=" * 80)
    print("CASCADEFLOW DIAGNOSTIC INTEGRATION TEST SUITE")
    print("=" * 80)

    # Detect available providers
    print("\n1. Detecting available providers...")
    print("-" * 80)
    providers = get_available_providers()

    if not providers:
        print("\n⚠️  No API providers detected (no API keys found)")
        print("   Running in MOCK MODE for offline testing")
        use_mock = True
    else:
        print(f"\n✓ Found {len(providers)} provider(s)")
        use_mock = False

    results = {}

    # Test 1: Basic integration
    if use_mock:
        print("\n" + "=" * 80)
        print("Running tests in MOCK MODE")
        print("=" * 80)
        results["mock"] = await test_with_mock_provider()
    else:
        models = create_models_from_providers(providers)
        if len(models) >= 2:
            results["real"] = await test_with_real_providers(models)
        else:
            print("\n⚠️  Need 2+ models for cascade testing")
            print("   Falling back to mock mode")
            results["mock"] = await test_with_mock_provider()

    # Test 2: Quality system validation (only with real providers)
    if not use_mock:
        results["quality"] = await test_quality_system_validation()

    # Final summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {test_name:20s}: {status}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("RESULT: ✓ ALL TESTS PASSED")
    else:
        print("RESULT: ✗ SOME TESTS FAILED")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
