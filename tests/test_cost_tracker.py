"""Test suite for cost tracking system (v0.2.0)."""

import platform
import time
from datetime import timedelta

import pytest

from cascadeflow.telemetry import BudgetConfig, CostTracker


class TestBudgetConfig:
    """Test BudgetConfig dataclass."""

    def test_create_daily_budget(self):
        """Test creating a daily budget only."""
        config = BudgetConfig(daily=1.0)
        assert config.daily == 1.0
        assert config.weekly is None
        assert config.monthly is None
        assert config.total is None
        assert config.has_any_limit()

    def test_create_multiple_periods(self):
        """Test creating budget with multiple periods."""
        config = BudgetConfig(daily=1.0, weekly=5.0, monthly=20.0)
        assert config.daily == 1.0
        assert config.weekly == 5.0
        assert config.monthly == 20.0
        assert config.total is None
        assert config.has_any_limit()

    def test_create_no_limits(self):
        """Test creating budget with no limits."""
        config = BudgetConfig()
        assert not config.has_any_limit()

    def test_repr(self):
        """Test human-readable representation."""
        config = BudgetConfig(daily=0.10, weekly=0.50)
        repr_str = repr(config)
        assert "daily=$0.10" in repr_str
        assert "weekly=$0.50" in repr_str

    def test_repr_no_limits(self):
        """Test repr with no limits."""
        config = BudgetConfig()
        assert repr(config) == "BudgetConfig(no limits)"


class TestCostTrackerBackwardCompatibility:
    """Test backward compatibility with v0.1.1."""

    def test_basic_cost_tracking_v011(self):
        """Test basic cost tracking without user tracking (v0.1.1 style)."""
        tracker = CostTracker()
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=100,
            cost=0.003,
        )

        assert tracker.total_cost == 0.003
        assert tracker.by_model["gpt-4"] == 0.003
        assert tracker.by_provider["openai"] == 0.003
        assert len(tracker.entries) == 1

    def test_budget_limit_v011(self):
        """Test global budget limit (v0.1.1 style)."""
        tracker = CostTracker(budget_limit=0.01)
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=1000,
            cost=0.005,
        )

        assert not tracker.budget_exceeded

        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=1000,
            cost=0.006,
        )

        assert tracker.budget_exceeded

    def test_get_summary_v011(self):
        """Test get_summary without user tracking (v0.1.1 style)."""
        tracker = CostTracker(budget_limit=1.0)
        tracker.add_cost(model="gpt-4", provider="openai", tokens=100, cost=0.003)

        summary = tracker.get_summary()
        assert summary["total_cost"] == 0.003
        assert summary["total_entries"] == 1
        assert summary["budget_limit"] == 1.0
        assert summary["budget_remaining"] == 0.997
        assert summary["budget_used_pct"] == 0.3

    def test_reset_v011(self):
        """Test reset without user tracking (v0.1.1 style)."""
        tracker = CostTracker()
        tracker.add_cost(model="gpt-4", provider="openai", tokens=100, cost=0.003)

        tracker.reset()

        assert tracker.total_cost == 0.0
        assert len(tracker.entries) == 0
        assert len(tracker.by_model) == 0
        assert len(tracker.by_user) == 0  # v0.2.0 fields also reset


class TestCostTrackerPerUserTracking:
    """Test per-user cost tracking (NEW in v0.2.0)."""

    def test_user_tracking_without_budget(self):
        """Test tracking costs per user without budget limits."""
        tracker = CostTracker()
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=100,
            cost=0.003,
            user_id="user_123",
        )

        assert tracker.by_user["user_123"] == 0.003
        assert len(tracker.user_entries["user_123"]) == 1
        assert tracker.total_cost == 0.003  # Global tracking still works

    def test_multiple_users(self):
        """Test tracking multiple users."""
        tracker = CostTracker()

        tracker.add_cost(model="gpt-4", provider="openai", tokens=100, cost=0.003, user_id="user_1")
        tracker.add_cost(
            model="gpt-3.5-turbo", provider="openai", tokens=500, cost=0.001, user_id="user_2"
        )
        tracker.add_cost(model="gpt-4", provider="openai", tokens=100, cost=0.003, user_id="user_1")

        assert tracker.by_user["user_1"] == 0.006
        assert tracker.by_user["user_2"] == 0.001
        assert tracker.total_cost == 0.007

    def test_get_all_users(self):
        """Test getting all tracked users."""
        tracker = CostTracker()

        tracker.add_cost(model="gpt-4", provider="openai", tokens=100, cost=0.003, user_id="user_1")
        tracker.add_cost(model="gpt-4", provider="openai", tokens=100, cost=0.003, user_id="user_2")

        users = tracker.get_all_users()
        assert len(users) == 2
        assert "user_1" in users
        assert "user_2" in users

    def test_get_user_summary_no_tier(self):
        """Test getting user summary without tier info."""
        tracker = CostTracker()
        tracker.add_cost(
            model="gpt-4", provider="openai", tokens=100, cost=0.003, user_id="user_123"
        )

        summary = tracker.get_user_summary("user_123")
        assert summary["user_id"] == "user_123"
        assert summary["total_cost"] == 0.003
        assert summary["total_entries"] == 1
        assert "budget_config" not in summary  # No tier provided


class TestUserBudgetTracking:
    """Test per-user budget tracking with limits (NEW in v0.2.0)."""

    def test_daily_budget_enforcement(self):
        """Test daily budget enforcement."""
        tracker = CostTracker(
            user_budgets={
                "free": BudgetConfig(daily=0.10),
            }
        )

        # Add cost below limit
        tracker.add_cost(
            model="gpt-3.5-turbo",
            provider="openai",
            tokens=1000,
            cost=0.05,
            user_id="user_123",
            user_tier="free",
        )

        summary = tracker.get_user_summary("user_123", "free")
        assert not summary["budget_exceeded"]

        # Add cost exceeding limit
        tracker.add_cost(
            model="gpt-3.5-turbo",
            provider="openai",
            tokens=2000,
            cost=0.10,
            user_id="user_123",
            user_tier="free",
        )

        summary = tracker.get_user_summary("user_123", "free")
        assert summary["budget_exceeded"]
        assert summary["period_costs"]["daily"]["exceeded"]

    def test_multiple_budget_periods(self):
        """Test tracking multiple budget periods."""
        tracker = CostTracker(
            user_budgets={
                "pro": BudgetConfig(daily=1.0, weekly=5.0, monthly=20.0),
            }
        )

        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=1000,
            cost=0.50,
            user_id="user_pro",
            user_tier="pro",
        )

        summary = tracker.get_user_summary("user_pro", "pro")
        assert "daily" in summary["period_costs"]
        assert "weekly" in summary["period_costs"]
        assert "monthly" in summary["period_costs"]

        # Check daily
        daily = summary["period_costs"]["daily"]
        assert daily["cost"] == 0.50
        assert daily["limit"] == 1.0
        assert daily["remaining"] == 0.50
        assert daily["used_pct"] == 50.0
        assert not daily["exceeded"]

    def test_total_lifetime_budget(self):
        """Test total lifetime budget (no reset)."""
        tracker = CostTracker(
            user_budgets={
                "trial": BudgetConfig(total=5.0),
            }
        )

        # Add costs over time
        for _ in range(10):
            tracker.add_cost(
                model="gpt-4",
                provider="openai",
                tokens=1000,
                cost=0.60,
                user_id="trial_user",
                user_tier="trial",
            )

        summary = tracker.get_user_summary("trial_user", "trial")
        assert abs(summary["total_cost"] - 6.0) < 0.001  # Allow floating point error
        assert summary["budget_exceeded"]  # Exceeded total budget

    def test_user_without_budget_config(self):
        """Test user with tier not in budget configs."""
        tracker = CostTracker(
            user_budgets={
                "free": BudgetConfig(daily=0.10),
            }
        )

        # Add cost for tier not in configs
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=1000,
            cost=10.0,  # Large cost
            user_id="enterprise_user",
            user_tier="enterprise",  # Not in user_budgets
        )

        # Should track but not enforce budget
        assert tracker.by_user["enterprise_user"] == 10.0

    def test_budget_warning_threshold(self):
        """Test budget warning at 80% threshold."""
        tracker = CostTracker(
            user_budgets={
                "free": BudgetConfig(daily=1.0),
            },
            warn_threshold=0.8,
        )

        # Add cost to 85% of budget
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=1000,
            cost=0.85,
            user_id="user_123",
            user_tier="free",
        )

        # Should have warning but not exceeded
        summary = tracker.get_user_summary("user_123", "free")
        assert not summary["budget_exceeded"]
        # Warning tracked internally
        assert "free:daily" in tracker.user_budget_warned["user_123"]


class TestTimeBudgetResets:
    """Test time-based budget reset logic (NEW in v0.2.0)."""

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="Timing-sensitive test is flaky on Windows Python 3.10/3.11",
    )
    def test_daily_budget_reset(self):
        """Test daily budget resets after 24 hours."""
        tracker = CostTracker(
            user_budgets={
                "free": BudgetConfig(daily=0.10),
            }
        )

        # Add cost on day 1
        tracker.add_cost(
            model="gpt-3.5-turbo",
            provider="openai",
            tokens=1000,
            cost=0.08,
            user_id="user_123",
            user_tier="free",
        )

        # Simulate time passing (25 hours)
        user_id = "user_123"
        period_start = tracker.user_period_start[user_id]["daily"]
        tracker.user_period_start[user_id]["daily"] = period_start - timedelta(hours=25)

        # Add new cost (should trigger reset)
        tracker.add_cost(
            model="gpt-3.5-turbo",
            provider="openai",
            tokens=1000,
            cost=0.08,
            user_id="user_123",
            user_tier="free",
        )

        summary = tracker.get_user_summary("user_123", "free")
        # After reset, only new cost counted
        assert summary["period_costs"]["daily"]["cost"] == 0.08
        assert not summary["budget_exceeded"]

    def test_no_reset_for_total_budget(self):
        """Test that total budget never resets."""
        tracker = CostTracker(
            user_budgets={
                "trial": BudgetConfig(total=1.0),
            }
        )

        # Add costs
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=1000,
            cost=0.60,
            user_id="trial_user",
            user_tier="trial",
        )

        # Simulate time passing (should not reset)
        user_id = "trial_user"
        if "total" in tracker.user_period_start.get(user_id, {}):
            period_start = tracker.user_period_start[user_id]["total"]
            tracker.user_period_start[user_id]["total"] = period_start - timedelta(days=100)

        # Add more cost
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=1000,
            cost=0.60,
            user_id="trial_user",
            user_tier="trial",
        )

        # Total should accumulate (no reset)
        assert tracker.by_user["trial_user"] == 1.20


class TestCostTrackerPerformance:
    """Test performance characteristics."""

    def test_add_cost_performance(self):
        """Test that add_cost is fast (<1ms target)."""
        tracker = CostTracker(
            user_budgets={
                "free": BudgetConfig(daily=1.0, weekly=5.0, monthly=20.0),
            }
        )

        # Measure 100 add_cost calls
        start = time.perf_counter()
        for i in range(100):
            tracker.add_cost(
                model="gpt-4",
                provider="openai",
                tokens=100,
                cost=0.003,
                user_id=f"user_{i % 10}",  # 10 unique users
                user_tier="free",
            )
        elapsed = time.perf_counter() - start

        # Should average <1ms per call
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 1.0, f"add_cost took {avg_ms:.2f}ms on average (target: <1ms)"

    def test_memory_efficiency(self):
        """Test memory efficiency with many users."""
        tracker = CostTracker(
            user_budgets={
                "free": BudgetConfig(daily=1.0),
            }
        )

        # Add costs for 1000 users
        for i in range(1000):
            tracker.add_cost(
                model="gpt-4",
                provider="openai",
                tokens=100,
                cost=0.003,
                user_id=f"user_{i}",
                user_tier="free",
            )

        # Should track all users
        assert len(tracker.get_all_users()) == 1000
        assert abs(tracker.total_cost - 3.0) < 0.001  # Allow floating point error


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_cost(self):
        """Test handling zero cost."""
        tracker = CostTracker()
        tracker.add_cost(
            model="cached-gpt-4",
            provider="openai",
            tokens=100,
            cost=0.0,
            user_id="user_123",
        )

        assert tracker.by_user["user_123"] == 0.0

    def test_negative_cost(self):
        """Test handling negative cost (refund scenario)."""
        tracker = CostTracker()
        tracker.add_cost(model="gpt-4", provider="openai", tokens=100, cost=0.01)
        tracker.add_cost(model="refund", provider="openai", tokens=0, cost=-0.005)  # Refund

        assert tracker.total_cost == 0.005

    def test_user_id_without_tier(self):
        """Test user_id provided but no user_tier."""
        tracker = CostTracker(
            user_budgets={
                "free": BudgetConfig(daily=1.0),
            }
        )

        # Should track user but not check budget
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=1000,
            cost=10.0,
            user_id="user_123",
            # No user_tier
        )

        assert tracker.by_user["user_123"] == 10.0

    def test_empty_user_id(self):
        """Test empty user_id string."""
        tracker = CostTracker()
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=100,
            cost=0.003,
            user_id="",  # Empty string
        )

        # Should track with empty string as key
        assert tracker.by_user[""] == 0.003

    def test_get_user_summary_nonexistent_user(self):
        """Test getting summary for user with no costs."""
        tracker = CostTracker()
        summary = tracker.get_user_summary("nonexistent_user")

        assert summary["user_id"] == "nonexistent_user"
        assert summary["total_cost"] == 0.0
        assert summary["total_entries"] == 0


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_saas_free_tier_scenario(self):
        """Test Sarah's SaaS free tier scenario from planning docs."""
        # Sarah's SaaS: Free tier with $0.10/day limit
        tracker = CostTracker(
            user_budgets={
                "free": BudgetConfig(daily=0.10),
                "pro": BudgetConfig(daily=1.0, weekly=5.0),
            },
            warn_threshold=0.8,
        )

        # Free user makes 5 queries
        for _i in range(5):
            tracker.add_cost(
                model="gpt-3.5-turbo",
                provider="openai",
                tokens=500,
                cost=0.015,
                user_id="free_user_1",
                user_tier="free",
            )

        # Check if exceeded (5 * 0.015 = 0.075, under limit)
        summary = tracker.get_user_summary("free_user_1", "free")
        assert not summary["budget_exceeded"]

        # One more query pushes over
        tracker.add_cost(
            model="gpt-3.5-turbo",
            provider="openai",
            tokens=500,
            cost=0.03,
            user_id="free_user_1",
            user_tier="free",
        )

        summary = tracker.get_user_summary("free_user_1", "free")
        assert summary["budget_exceeded"]
        assert summary["total_cost"] == 0.105

    def test_multi_tier_tracking(self):
        """Test tracking multiple tiers simultaneously."""
        tracker = CostTracker(
            user_budgets={
                "free": BudgetConfig(daily=0.10),
                "pro": BudgetConfig(daily=1.0),
                "enterprise": BudgetConfig(daily=10.0),
            }
        )

        # Add costs for different tiers
        tracker.add_cost(
            model="gpt-3.5-turbo",
            provider="openai",
            tokens=500,
            cost=0.05,
            user_id="free_1",
            user_tier="free",
        )
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=500,
            cost=0.50,
            user_id="pro_1",
            user_tier="pro",
        )
        tracker.add_cost(
            model="gpt-4",
            provider="openai",
            tokens=5000,
            cost=5.0,
            user_id="ent_1",
            user_tier="enterprise",
        )

        # Check each tier
        free_summary = tracker.get_user_summary("free_1", "free")
        assert not free_summary["budget_exceeded"]

        pro_summary = tracker.get_user_summary("pro_1", "pro")
        assert not pro_summary["budget_exceeded"]

        ent_summary = tracker.get_user_summary("ent_1", "enterprise")
        assert not ent_summary["budget_exceeded"]

        # Global total should be sum
        assert tracker.total_cost == 5.55


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
