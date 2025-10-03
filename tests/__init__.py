"""Quick test to verify all imports work after __init__.py update."""

def test_core_imports():
    """Test core configuration imports."""
    from cascadeflow import (
        ModelConfig,
        CascadeConfig,
        UserTier,
        CascadeAgent,
        CascadeResult
    )
    print("✓ Core imports working")

def test_day42_config_imports():
    """Test Day 4.2 configuration imports."""
    from cascadeflow import (
        WorkflowProfile,
        LatencyProfile,
        OptimizationWeights,
        DEFAULT_TIERS,
        EXAMPLE_WORKFLOWS
    )
    print("✓ Day 4.2 config imports working")
    print(f"  - Found {len(DEFAULT_TIERS)} default tiers")
    print(f"  - Found {len(EXAMPLE_WORKFLOWS)} example workflows")

def test_intelligence_imports():
    """Test intelligence layer imports."""
    from cascadeflow import (
        ComplexityDetector,
        QueryComplexity,
        DomainDetector,
        ModelScorer,
        LatencyAwareExecutionPlanner,
        ExecutionStrategy,
        ExecutionPlan
    )
    print("✓ Intelligence layer imports working")

def test_speculative_imports():
    """Test speculative cascade imports."""
    from cascadeflow import (
        SpeculativeCascade,
        DeferralStrategy,
        FlexibleDeferralRule,
        SpeculativeResult
    )
    print("✓ Speculative cascade imports working")

def test_features_imports():
    """Test supporting features imports."""
    from cascadeflow import (
        CallbackManager,
        CallbackEvent,
        CallbackData,
        ResponseCache,
        StreamManager,
        CascadePresets
    )
    print("✓ Supporting features imports working")

def test_providers_imports():
    """Test provider imports."""
    from cascadeflow import (
        ModelResponse,
        BaseProvider,
        PROVIDER_REGISTRY
    )
    print("✓ Provider imports working")

def test_utils_imports():
    """Test utility imports."""
    from cascadeflow import (
        setup_logging,
        format_cost,
        estimate_tokens
    )
    print("✓ Utility imports working")

def test_exceptions_imports():
    """Test exception imports."""
    from cascadeflow import (
        CascadeFlowError,
        ConfigError,
        ProviderError,
        ModelError,
        BudgetExceededError,
        RateLimitError,
        QualityThresholdError,
        RoutingError,
        ValidationError
    )
    print("✓ Exception imports working")

def test_version():
    """Test version info."""
    from cascadeflow import __version__
    print(f"✓ Version: {__version__}")
    assert __version__ == "0.4.2"

if __name__ == "__main__":
    print("Testing CascadeFlow imports...\n")

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