"""Test suite for enforcement callbacks (v0.2.0)."""

import pytest

from cascadeflow.telemetry import (
    EnforcementAction,
    EnforcementCallbacks,
    EnforcementContext,
    graceful_degradation,
    strict_budget_enforcement,
    tier_based_enforcement,
)


class TestEnforcementAction:
    """Test EnforcementAction enum."""

    def test_action_values(self):
        """Test that action values are correct."""
        assert EnforcementAction.ALLOW.value == "allow"
        assert EnforcementAction.WARN.value == "warn"
        assert EnforcementAction.BLOCK.value == "block"
        assert EnforcementAction.DEGRADE.value == "degrade"

    def test_action_comparison(self):
        """Test that actions can be compared."""
        assert EnforcementAction.ALLOW == EnforcementAction.ALLOW
        assert EnforcementAction.BLOCK != EnforcementAction.ALLOW


class TestEnforcementContext:
    """Test EnforcementContext dataclass."""

    def test_create_minimal_context(self):
        """Test creating context with minimal fields."""
        context = EnforcementContext(user_id="user_123")
        assert context.user_id == "user_123"
        assert context.user_tier is None
        assert context.current_cost == 0.0
        assert context.budget_exceeded is False

    def test_create_full_context(self):
        """Test creating context with all fields."""
        context = EnforcementContext(
            user_id="user_123",
            user_tier="free",
            current_cost=0.08,
            estimated_cost=0.03,
            total_cost=0.15,
            budget_limit=0.10,
            budget_used_pct=80.0,
            budget_exceeded=False,
            period_name="daily",
            model="gpt-4",
            provider="openai",
            query="test query",
            tokens=1000,
            metadata={"app": "web"},
        )

        assert context.user_id == "user_123"
        assert context.user_tier == "free"
        assert context.current_cost == 0.08
        assert context.estimated_cost == 0.03
        assert context.total_cost == 0.15
        assert context.budget_limit == 0.10
        assert context.budget_used_pct == 80.0
        assert context.budget_exceeded is False
        assert context.period_name == "daily"
        assert context.model == "gpt-4"
        assert context.provider == "openai"
        assert context.query == "test query"
        assert context.tokens == 1000
        assert context.metadata["app"] == "web"

    def test_context_repr(self):
        """Test context string representation."""
        context = EnforcementContext(
            user_id="user_123",
            user_tier="free",
            current_cost=0.08,
            budget_limit=0.10,
            budget_used_pct=80.0,
        )

        repr_str = repr(context)
        assert "user_123" in repr_str
        assert "free" in repr_str
        assert "0.08" in repr_str
        assert "0.10" in repr_str or "0.1" in repr_str
        assert "80.0%" in repr_str


class TestEnforcementCallbacks:
    """Test EnforcementCallbacks class."""

    def test_create_callbacks(self):
        """Test creating callbacks manager."""
        callbacks = EnforcementCallbacks()
        assert len(callbacks.callbacks) == 0
        assert callbacks._call_count == 0

    def test_register_callback(self):
        """Test registering a callback."""
        callbacks = EnforcementCallbacks()

        def my_callback(context):
            return EnforcementAction.ALLOW

        callbacks.register(my_callback)
        assert len(callbacks.callbacks) == 1
        assert callbacks.callbacks[0] == my_callback

    def test_multiple_callbacks(self):
        """Test registering multiple callbacks."""
        callbacks = EnforcementCallbacks()

        def callback1(context):
            return EnforcementAction.ALLOW

        def callback2(context):
            return EnforcementAction.WARN

        callbacks.register(callback1)
        callbacks.register(callback2)

        assert len(callbacks.callbacks) == 2

    def test_unregister_callback(self):
        """Test unregistering a callback."""
        callbacks = EnforcementCallbacks()

        def my_callback(context):
            return EnforcementAction.ALLOW

        callbacks.register(my_callback)
        assert len(callbacks.callbacks) == 1

        callbacks.unregister(my_callback)
        assert len(callbacks.callbacks) == 0

    def test_clear_callbacks(self):
        """Test clearing all callbacks."""
        callbacks = EnforcementCallbacks()

        def callback1(context):
            return EnforcementAction.ALLOW

        def callback2(context):
            return EnforcementAction.WARN

        callbacks.register(callback1)
        callbacks.register(callback2)
        assert len(callbacks.callbacks) == 2

        callbacks.clear()
        assert len(callbacks.callbacks) == 0

    def test_check_no_callbacks(self):
        """Test checking with no callbacks registered."""
        callbacks = EnforcementCallbacks()
        context = EnforcementContext(user_id="user_123")

        action = callbacks.check(context)
        assert action == EnforcementAction.ALLOW

    def test_check_allow_callback(self):
        """Test callback that returns ALLOW."""
        callbacks = EnforcementCallbacks()

        def allow_callback(context):
            return EnforcementAction.ALLOW

        callbacks.register(allow_callback)

        context = EnforcementContext(user_id="user_123")
        action = callbacks.check(context)
        assert action == EnforcementAction.ALLOW

    def test_check_block_callback(self):
        """Test callback that returns BLOCK."""
        callbacks = EnforcementCallbacks()

        def block_callback(context):
            return EnforcementAction.BLOCK

        callbacks.register(block_callback)

        context = EnforcementContext(user_id="user_123")
        action = callbacks.check(context)
        assert action == EnforcementAction.BLOCK

    def test_first_non_allow_wins(self):
        """Test that first non-ALLOW callback stops execution."""
        callbacks = EnforcementCallbacks()
        executed = []

        def callback1(context):
            executed.append(1)
            return EnforcementAction.ALLOW

        def callback2(context):
            executed.append(2)
            return EnforcementAction.BLOCK  # This should stop execution

        def callback3(context):
            executed.append(3)  # This should NOT execute
            return EnforcementAction.ALLOW

        callbacks.register(callback1)
        callbacks.register(callback2)
        callbacks.register(callback3)

        context = EnforcementContext(user_id="user_123")
        action = callbacks.check(context)

        assert action == EnforcementAction.BLOCK
        assert executed == [1, 2]  # callback3 not executed

    def test_callback_error_handling(self):
        """Test that callback errors are handled gracefully."""
        callbacks = EnforcementCallbacks()

        def bad_callback(context):
            raise ValueError("Test error")

        def good_callback(context):
            return EnforcementAction.ALLOW

        callbacks.register(bad_callback)
        callbacks.register(good_callback)

        context = EnforcementContext(user_id="user_123")
        action = callbacks.check(context)

        # Should continue despite error
        assert action == EnforcementAction.ALLOW

    def test_invalid_return_value(self):
        """Test callback returning invalid value."""
        callbacks = EnforcementCallbacks()

        def invalid_callback(context):
            return "invalid"  # Not an EnforcementAction

        def valid_callback(context):
            return EnforcementAction.BLOCK

        callbacks.register(invalid_callback)
        callbacks.register(valid_callback)

        context = EnforcementContext(user_id="user_123")
        action = callbacks.check(context)

        # Should skip invalid and execute valid
        assert action == EnforcementAction.BLOCK

    def test_get_stats(self):
        """Test getting callback statistics."""
        callbacks = EnforcementCallbacks()

        def callback1(context):
            return EnforcementAction.ALLOW

        def callback2(context):
            return EnforcementAction.WARN

        callbacks.register(callback1)
        callbacks.register(callback2)

        # Execute checks
        context = EnforcementContext(user_id="user_123")
        callbacks.check(context)
        callbacks.check(context)

        stats = callbacks.get_stats()
        assert stats["registered_callbacks"] == 2
        assert stats["total_checks"] == 2


class TestBuiltInCallbacks:
    """Test built-in enforcement callbacks."""

    def test_strict_budget_enforcement_allow(self):
        """Test strict enforcement allows under budget."""
        context = EnforcementContext(
            user_id="user_123",
            budget_used_pct=50.0,
            budget_exceeded=False,
        )

        action = strict_budget_enforcement(context)
        assert action == EnforcementAction.ALLOW

    def test_strict_budget_enforcement_warn(self):
        """Test strict enforcement warns at 80%."""
        context = EnforcementContext(
            user_id="user_123",
            budget_used_pct=85.0,
            budget_exceeded=False,
        )

        action = strict_budget_enforcement(context)
        assert action == EnforcementAction.WARN

    def test_strict_budget_enforcement_block(self):
        """Test strict enforcement blocks when exceeded."""
        context = EnforcementContext(
            user_id="user_123",
            budget_used_pct=105.0,
            budget_exceeded=True,
        )

        action = strict_budget_enforcement(context)
        assert action == EnforcementAction.BLOCK

    def test_graceful_degradation_allow(self):
        """Test graceful degradation allows under budget."""
        context = EnforcementContext(
            user_id="user_123",
            budget_used_pct=70.0,
            budget_exceeded=False,
        )

        action = graceful_degradation(context)
        assert action == EnforcementAction.ALLOW

    def test_graceful_degradation_warn(self):
        """Test graceful degradation warns at 80%."""
        context = EnforcementContext(
            user_id="user_123",
            budget_used_pct=85.0,
            budget_exceeded=False,
        )

        action = graceful_degradation(context)
        assert action == EnforcementAction.WARN

    def test_graceful_degradation_degrade(self):
        """Test graceful degradation degrades at 90%."""
        context = EnforcementContext(
            user_id="user_123",
            budget_used_pct=95.0,
            budget_exceeded=False,
        )

        action = graceful_degradation(context)
        assert action == EnforcementAction.DEGRADE

    def test_graceful_degradation_block(self):
        """Test graceful degradation blocks when exceeded."""
        context = EnforcementContext(
            user_id="user_123",
            budget_used_pct=105.0,
            budget_exceeded=True,
        )

        action = graceful_degradation(context)
        assert action == EnforcementAction.BLOCK

    def test_tier_based_free_allow(self):
        """Test tier-based enforcement allows free tier under budget."""
        context = EnforcementContext(
            user_id="user_123",
            user_tier="free",
            budget_used_pct=70.0,
            budget_exceeded=False,
        )

        action = tier_based_enforcement(context)
        assert action == EnforcementAction.ALLOW

    def test_tier_based_free_warn(self):
        """Test tier-based enforcement warns free tier at 80%."""
        context = EnforcementContext(
            user_id="user_123",
            user_tier="free",
            budget_used_pct=85.0,
            budget_exceeded=False,
        )

        action = tier_based_enforcement(context)
        assert action == EnforcementAction.WARN

    def test_tier_based_free_block(self):
        """Test tier-based enforcement blocks free tier when exceeded."""
        context = EnforcementContext(
            user_id="user_123",
            user_tier="free",
            budget_used_pct=105.0,
            budget_exceeded=True,
        )

        action = tier_based_enforcement(context)
        assert action == EnforcementAction.BLOCK

    def test_tier_based_pro_degrade(self):
        """Test tier-based enforcement degrades pro tier when exceeded."""
        context = EnforcementContext(
            user_id="user_pro",
            user_tier="pro",
            budget_used_pct=105.0,
            budget_exceeded=True,
        )

        action = tier_based_enforcement(context)
        assert action == EnforcementAction.DEGRADE  # Pro degrades, not blocks

    def test_tier_based_pro_warn(self):
        """Test tier-based enforcement warns pro tier at 90%."""
        context = EnforcementContext(
            user_id="user_pro",
            user_tier="pro",
            budget_used_pct=95.0,
            budget_exceeded=False,
        )

        action = tier_based_enforcement(context)
        assert action == EnforcementAction.WARN

    def test_tier_based_enterprise_warn_only(self):
        """Test tier-based enforcement only warns enterprise (never blocks)."""
        # Enterprise at 105% - should only warn
        context = EnforcementContext(
            user_id="user_ent",
            user_tier="enterprise",
            budget_used_pct=105.0,
            budget_exceeded=True,  # Even when exceeded
        )

        action = tier_based_enforcement(context)
        assert action == EnforcementAction.WARN  # Never blocks enterprise


class TestRealWorldScenarios:
    """Test real-world enforcement scenarios."""

    def test_saas_free_tier_enforcement(self):
        """Test SaaS free tier with strict enforcement."""
        callbacks = EnforcementCallbacks()
        callbacks.register(strict_budget_enforcement)

        # User at 50% - should allow
        context = EnforcementContext(
            user_id="free_user_1",
            user_tier="free",
            current_cost=0.05,
            budget_limit=0.10,
            budget_used_pct=50.0,
            budget_exceeded=False,
        )
        assert callbacks.check(context) == EnforcementAction.ALLOW

        # User at 85% - should warn
        context.budget_used_pct = 85.0
        assert callbacks.check(context) == EnforcementAction.WARN

        # User at 105% - should block
        context.budget_used_pct = 105.0
        context.budget_exceeded = True
        assert callbacks.check(context) == EnforcementAction.BLOCK

    def test_custom_callback_integration(self):
        """Test custom callback for specific business logic."""
        callbacks = EnforcementCallbacks()

        # Custom callback: Block GPT-4 for free tier, allow GPT-3.5
        def block_expensive_models_for_free(context):
            if context.user_tier == "free" and context.model == "gpt-4":
                return EnforcementAction.BLOCK
            return EnforcementAction.ALLOW

        callbacks.register(block_expensive_models_for_free)

        # Free user with GPT-4 - should block
        context = EnforcementContext(
            user_id="free_user",
            user_tier="free",
            model="gpt-4",
            budget_exceeded=False,
        )
        assert callbacks.check(context) == EnforcementAction.BLOCK

        # Free user with GPT-3.5 - should allow
        context.model = "gpt-3.5-turbo"
        assert callbacks.check(context) == EnforcementAction.ALLOW

    def test_multi_callback_chain(self):
        """Test chaining multiple callbacks."""
        callbacks = EnforcementCallbacks()

        # Callback 1: Block if budget exceeded
        def check_budget(context):
            if context.budget_exceeded:
                return EnforcementAction.BLOCK
            return EnforcementAction.ALLOW

        # Callback 2: Degrade if using expensive model near budget
        def check_model_cost(context):
            if context.budget_used_pct > 80 and context.model == "gpt-4":
                return EnforcementAction.DEGRADE
            return EnforcementAction.ALLOW

        callbacks.register(check_budget)
        callbacks.register(check_model_cost)

        # Scenario 1: Budget exceeded - first callback blocks
        context = EnforcementContext(
            user_id="user_1",
            budget_exceeded=True,
            model="gpt-4",
        )
        assert callbacks.check(context) == EnforcementAction.BLOCK

        # Scenario 2: Budget OK, expensive model at 85% - second callback degrades
        context.budget_exceeded = False
        context.budget_used_pct = 85.0
        assert callbacks.check(context) == EnforcementAction.DEGRADE

        # Scenario 3: Budget OK, cheap model - both allow
        context.model = "gpt-3.5-turbo"
        context.budget_used_pct = 50.0
        assert callbacks.check(context) == EnforcementAction.ALLOW


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
