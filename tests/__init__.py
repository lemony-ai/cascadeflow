"""Quick test to verify all imports work after __init__.py update."""


def test_core_imports():
    """Test core configuration imports."""
    from cascadeflow import CascadeAgent, CascadeConfig, CascadeResult, ModelConfig, UserTier

    print("✓ Core imports working")


def test_day42_config_imports():
    """Test Day 4.2 configuration imports."""
    from cascadeflow import (
        DEFAULT_TIERS,
        EXAMPLE_WORKFLOWS,
        LatencyProfile,
        OptimizationWeights,
        WorkflowProfile,
    )

    print("✓ Day 4.2 config imports working")
    print(f"  - Found {len(DEFAULT_TIERS)} default tiers")
    print(f"  - Found {len(EXAMPLE_WORKFLOWS)} example workflows")


def test_intelligence_imports():
    """Test intelligence layer imports."""
    from cascadeflow import (
        ComplexityDetector,
        DomainDetector,
        ExecutionPlan,
        ExecutionStrategy,
        LatencyAwareExecutionPlanner,
        ModelScorer,
        QueryComplexity,
    )

    print("✓ Intelligence layer imports working")


def test_speculative_imports():
    """Test speculative cascade imports."""
    from cascadeflow import (
        DeferralStrategy,
        FlexibleDeferralRule,
        SpeculativeCascade,
        SpeculativeResult,
    )

    print("✓ Speculative cascade imports working")


def test_features_imports():
    """Test supporting features imports."""
    from cascadeflow import (
        CallbackData,
        CallbackEvent,
        CallbackManager,
        CascadePresets,
        ResponseCache,
        StreamManager,
    )

    print("✓ Supporting features imports working")


def test_providers_imports():
    """Test provider imports."""
    from cascadeflow import PROVIDER_REGISTRY, BaseProvider, ModelResponse

    print("✓ Provider imports working")


def test_utils_imports():
    """Test utility imports."""
    from cascadeflow import estimate_tokens, format_cost, setup_logging

    print("✓ Utility imports working")


def test_exceptions_imports():
    """Test exception imports."""
    from cascadeflow import (
        BudgetExceededError,
        cascadeflowError,
        ConfigError,
        ModelError,
        ProviderError,
        QualityThresholdError,
        RateLimitError,
        RoutingError,
        ValidationError,
    )

    print("✓ Exception imports working")


def test_version():
    """Test version info."""
    from cascadeflow import __version__

    print(f"✓ Version: {__version__}")
    assert __version__ == "0.4.2"


if __name__ == "__main__":
    print("Testing cascadeflow imports...\n")

    try:
        test_core_imports()
        test_day42_config_imports()
        test_intelligence_imports()
        test_speculative_imports()
        test_features_imports()
        test_providers_imports()
        test_utils_imports()
        test_exceptions_imports()
        test_version()

        print("\n✅ All imports successful!")

    except ImportError as e:
        print(f"\n❌ Import failed: {e}")
        import traceback

        traceback.print_exc()
