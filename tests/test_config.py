"""
Test suite for enhanced config.py (Day 4.2)

Tests:
- LatencyProfile
- OptimizationWeights
- Enhanced UserTier
- WorkflowProfile
- DEFAULT_TIERS
"""

import pytest
from cascadeflow.config import (
    DEFAULT_TIERS,
    EXAMPLE_WORKFLOWS,
    LatencyProfile,
    OptimizationWeights,
)


class TestLatencyProfile:
    """Test LatencyProfile dataclass."""

    def test_basic_creation(self):
        profile = LatencyProfile(
            max_total_ms=1500,
            max_per_model_ms=1000,
            prefer_parallel=True,
            skip_cascade_threshold=1000,
        )
        assert profile.max_total_ms == 1500
        assert profile.max_per_model_ms == 1000
        assert profile.prefer_parallel is True
        assert profile.skip_cascade_threshold == 1000

    def test_tight_latency_profile(self):
        """Enterprise-style tight latency."""
        profile = LatencyProfile(
            max_total_ms=1000,
            max_per_model_ms=800,
            prefer_parallel=True,
            skip_cascade_threshold=900,
        )
        assert profile.max_total_ms < 1500
        assert profile.prefer_parallel is True


class TestOptimizationWeights:
    """Test OptimizationWeights validation."""

    def test_valid_weights(self):
        weights = OptimizationWeights(cost=0.20, speed=0.50, quality=0.30)
        assert weights.cost == 0.20
        assert weights.speed == 0.50
        assert weights.quality == 0.30

    def test_weights_sum_to_one(self):
        """Weights must sum to 1.0."""
        weights = OptimizationWeights(cost=0.3, speed=0.4, quality=0.3)
        total = weights.cost + weights.speed + weights.quality
        assert 0.99 <= total <= 1.01

    def test_invalid_weights(self):
        """Weights that don't sum to 1.0 should raise error."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            OptimizationWeights(cost=0.5, speed=0.3, quality=0.1)

    def test_cost_optimized(self):
        """Cost-first optimization."""
        weights = OptimizationWeights(cost=0.70, speed=0.15, quality=0.15)
        assert weights.cost > weights.speed
        assert weights.cost > weights.quality

    def test_speed_optimized(self):
        """Speed-first optimization."""
        weights = OptimizationWeights(cost=0.10, speed=0.70, quality=0.20)
        assert weights.speed > weights.cost
        assert weights.speed > weights.quality


class TestEnhancedUserTier:
    """Test enhanced UserTier with latency awareness."""

    def test_free_tier(self):
        tier = DEFAULT_TIERS["free"]
        assert tier.name == "free"
        assert tier.latency.max_total_ms == 15000
        assert tier.optimization.cost >= 0.7
        assert tier.max_budget <= 0.001

    def test_standard_tier(self):
        tier = DEFAULT_TIERS["standard"]
        assert tier.name == "standard"
        assert tier.latency.max_total_ms == 8000
        assert tier.max_budget == 0.01
        assert tier.enable_caching is True

    def test_premium_tier(self):
        tier = DEFAULT_TIERS["premium"]
        assert tier.name == "premium"
        assert tier.latency.max_total_ms == 3000
        assert tier.latency.prefer_parallel is True
        assert tier.enable_parallel is True
        assert tier.enable_streaming is True

    def test_enterprise_tier(self):
        tier = DEFAULT_TIERS["enterprise"]
        assert tier.name == "enterprise"
        assert tier.latency.max_total_ms == 1500
        assert tier.optimization.speed >= 0.6
        assert tier.enable_parallel is True
        assert tier.parallel_race_count == 3

    def test_tier_quality_thresholds(self):
        """Each tier should have quality thresholds."""
        for _tier_name, tier in DEFAULT_TIERS.items():
            assert 0 <= tier.quality_threshold <= 1
            assert tier.max_budget > 0
            if tier.target_quality:
                assert tier.target_quality >= tier.quality_threshold

    def test_tier_to_dict(self):
        tier = DEFAULT_TIERS["premium"]
        tier_dict = tier.to_dict()
        assert "name" in tier_dict
        assert "optimization" in tier_dict
        assert "latency" in tier_dict
        assert tier_dict["optimization"]["speed"] == 0.50


class TestWorkflowProfile:
    """Test WorkflowProfile configurations."""

    def test_draft_mode(self):
        workflow = EXAMPLE_WORKFLOWS["draft_mode"]
        assert workflow.name == "draft_mode"
        assert workflow.max_budget_override is not None
        assert workflow.max_budget_override < 0.001
        assert workflow.quality_threshold_override == 0.50

    def test_production_workflow(self):
        workflow = EXAMPLE_WORKFLOWS["production"]
        assert workflow.name == "production"
        assert workflow.quality_threshold_override == 0.85
        assert workflow.enable_caching is True

    def test_critical_workflow(self):
        workflow = EXAMPLE_WORKFLOWS["critical"]
        assert workflow.name == "critical"
        assert workflow.quality_threshold_override == 0.90
        assert workflow.optimization_override is not None
        assert workflow.optimization_override.quality >= 0.6

    def test_realtime_workflow(self):
        workflow = EXAMPLE_WORKFLOWS["realtime"]
        assert workflow.name == "realtime"
        assert workflow.latency_override is not None
        assert workflow.latency_override.max_total_ms < 1000
        assert workflow.optimization_override.speed >= 0.7

    def test_batch_processing(self):
        workflow = EXAMPLE_WORKFLOWS["batch_processing"]
        assert workflow.name == "batch_processing"
        assert workflow.latency_override.max_total_ms >= 30000
        assert workflow.optimization_override.cost >= 0.7


class TestDefaultTiers:
    """Test DEFAULT_TIERS dictionary."""

    def test_all_tiers_present(self):
        expected_tiers = ["free", "standard", "premium", "enterprise"]
        for tier_name in expected_tiers:
            assert tier_name in DEFAULT_TIERS

    def test_tier_hierarchy(self):
        """Higher tiers should have better latency/budget."""
        free = DEFAULT_TIERS["free"]
        standard = DEFAULT_TIERS["standard"]
        premium = DEFAULT_TIERS["premium"]
        enterprise = DEFAULT_TIERS["enterprise"]

        # Latency should improve
        assert free.latency.max_total_ms > standard.latency.max_total_ms
        assert standard.latency.max_total_ms > premium.latency.max_total_ms
        assert premium.latency.max_total_ms > enterprise.latency.max_total_ms

        # Budget should increase
        assert free.max_budget < standard.max_budget
        assert standard.max_budget < premium.max_budget
        assert premium.max_budget < enterprise.max_budget


class TestExampleWorkflows:
    """Test EXAMPLE_WORKFLOWS dictionary."""

    def test_all_workflows_present(self):
        expected = ["draft_mode", "production", "critical", "realtime", "batch_processing"]
        for workflow_name in expected:
            assert workflow_name in EXAMPLE_WORKFLOWS

    def test_workflow_priorities(self):
        """Different workflows should have different priorities."""
        draft = EXAMPLE_WORKFLOWS["draft_mode"]
        critical = EXAMPLE_WORKFLOWS["critical"]
        realtime = EXAMPLE_WORKFLOWS["realtime"]

        # Draft mode: cost priority
        assert draft.optimization_override.cost >= 0.8

        # Critical: quality priority
        assert critical.optimization_override.quality >= 0.6

        # Realtime: speed priority
        assert realtime.optimization_override.speed >= 0.7


class TestConfigIntegration:
    """Test how components work together."""

    def test_tier_with_workflow_override(self):
        """Workflow should be able to override tier settings."""
        tier = DEFAULT_TIERS["standard"]
        workflow = EXAMPLE_WORKFLOWS["critical"]

        assert workflow.quality_threshold_override > tier.quality_threshold

    def test_optimization_weights_consistency(self):
        """All optimization weights should sum to 1.0."""
        for tier_name, tier in DEFAULT_TIERS.items():
            total = tier.optimization.cost + tier.optimization.speed + tier.optimization.quality
            assert 0.99 <= total <= 1.01, f"{tier_name} weights don't sum to 1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
