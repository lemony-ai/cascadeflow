# test_merged_config.py
"""Test the merged configuration."""

from cascadeflow.config import (
    DEFAULT_TIERS,
    EXAMPLE_WORKFLOWS,
    LatencyProfile,
    ModelConfig,
    OptimizationWeights,
    UserTier,
)


def test_backwards_compatibility():
    """Test that old code still works."""
    print("Testing backwards compatibility...")

    # Old way still works
    tier = UserTier(
        name="test",
        latency=LatencyProfile(2000, 1500, True, 1500),
        optimization=OptimizationWeights(0.2, 0.5, 0.3),
        max_budget=0.05,
    )

    # Old methods still work
    assert tier.allows_model("gpt-4")
    config_dict = tier.to_cascade_config()
    assert "max_budget" in config_dict
    assert "use_speculative" in config_dict

    print("✓ Backwards compatibility OK")


def test_model_config():
    """Test ModelConfig with new fields."""
    print("Testing ModelConfig...")

    model = ModelConfig(
        name="gpt-4", provider="openai", cost=0.03, speed_ms=1500, quality_score=0.9  # NEW  # NEW
    )

    assert model.speed_ms == 1500
    assert model.quality_score == 0.9
    print("✓ ModelConfig works with new fields")


def test_new_features():
    """Test new features."""
    print("Testing new features...")

    # Test DEFAULT_TIERS
    assert "free" in DEFAULT_TIERS
    free_tier = DEFAULT_TIERS["free"]
    assert free_tier.optimization.cost == 0.70

    # Test EXAMPLE_WORKFLOWS
    assert "draft_mode" in EXAMPLE_WORKFLOWS
    draft = EXAMPLE_WORKFLOWS["draft_mode"]
    assert draft.max_budget_override == 0.0001

    print("✓ New features work")


def test_enhanced_usertier():
    """Test enhanced UserTier."""
    print("Testing enhanced UserTier...")

    tier = DEFAULT_TIERS["premium"]

    # New methods
    tier_dict = tier.to_dict()
    assert "optimization" in tier_dict
    assert "latency" in tier_dict

    # Latency profile
    assert tier.latency.max_total_ms == 3000
    assert tier.latency.prefer_parallel

    # Optimization weights
    assert tier.optimization.speed == 0.50  # Speed priority

    print("✓ Enhanced UserTier works")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Testing Merged Configuration")
    print("=" * 60 + "\n")

    test_backwards_compatibility()
    test_model_config()
    test_new_features()
    test_enhanced_usertier()

    print("\n" + "=" * 60)
    print("✅ All tests passed! Merge successful!")
    print("=" * 60 + "\n")

    # Show tier summary
    print("Default Tiers:")
    for name, tier in DEFAULT_TIERS.items():
        print(f"\n{name.upper()}:")
        print(f"  Budget: ${tier.max_budget}")
        print(f"  Latency: {tier.latency.max_total_ms}ms")
        print(
            f"  Weights: cost={tier.optimization.cost:.2f}, "
            f"speed={tier.optimization.speed:.2f}, "
            f"quality={tier.optimization.quality:.2f}"
        )
