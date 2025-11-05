"""
Basic Enforcement Example

Demonstrates how to use EnforcementCallbacks for budget enforcement.

Shows:
- Registering built-in callbacks
- Creating custom callbacks
- Checking enforcement actions
- Integration with CostTracker
"""

from cascadeflow.telemetry import (
    BudgetConfig,
    CostTracker,
    EnforcementAction,
    EnforcementCallbacks,
    EnforcementContext,
    strict_budget_enforcement,
)


def main():
    print("=" * 70)
    print("Basic Enforcement Example")
    print("=" * 70)
    print()

    # Step 1: Set up cost tracker with budgets
    print("Step 1: Configure cost tracker with user budgets")
    print("-" * 70)

    tracker = CostTracker(
        user_budgets={
            "free": BudgetConfig(daily=0.10),
            "pro": BudgetConfig(daily=1.0),
        }
    )

    print("✓ Created tracker with free ($0.10/day) and pro ($1.00/day) tiers")
    print()

    # Step 2: Set up enforcement callbacks
    print("Step 2: Configure enforcement callbacks")
    print("-" * 70)

    callbacks = EnforcementCallbacks(verbose=True)
    callbacks.register(strict_budget_enforcement)

    print("✓ Registered strict_budget_enforcement callback")
    print()

    # Step 3: Simulate free user making requests
    print("Step 3: Simulate free user making requests")
    print("-" * 70)

    # Add first cost (50% of budget)
    tracker.add_cost(
        model="gpt-4o-mini",  # Updated from deprecated gpt-3.5-turbo
        provider="openai",
        tokens=500,
        cost=0.05,
        user_id="free_user_001",
        user_tier="free",
    )

    # Check enforcement
    context = EnforcementContext(
        user_id="free_user_001",
        user_tier="free",
        current_cost=0.05,
        budget_limit=0.10,
        budget_used_pct=50.0,
        budget_exceeded=False,
    )

    action = callbacks.check(context)
    print(f"  Query 1: Cost=$0.05, Used=50% → Action: {action.value.upper()}")

    # Add second cost (85% of budget)
    tracker.add_cost(
        model="gpt-4o-mini",  # Updated from deprecated gpt-3.5-turbo
        provider="openai",
        tokens=500,
        cost=0.035,
        user_id="free_user_001",
        user_tier="free",
    )

    context.current_cost = 0.085
    context.budget_used_pct = 85.0
    action = callbacks.check(context)
    print(f"  Query 2: Cost=$0.085, Used=85% → Action: {action.value.upper()}")

    # Add third cost (exceeds budget)
    tracker.add_cost(
        model="gpt-4o-mini",  # Updated from deprecated gpt-3.5-turbo
        provider="openai",
        tokens=300,
        cost=0.02,
        user_id="free_user_001",
        user_tier="free",
    )

    context.current_cost = 0.105
    context.budget_used_pct = 105.0
    context.budget_exceeded = True
    action = callbacks.check(context)
    print(f"  Query 3: Cost=$0.105, Used=105% → Action: {action.value.upper()}")

    print()

    # Step 4: Handle enforcement action
    print("Step 4: Handle enforcement action in application")
    print("-" * 70)

    if action == EnforcementAction.BLOCK:
        print("  ⛔ Request BLOCKED - User exceeded daily budget")
        print("  → Show upgrade prompt to user")
    elif action == EnforcementAction.WARN:
        print("  ⚠️  Request ALLOWED with warning - Approaching budget limit")
        print("  → Log warning for monitoring")
    elif action == EnforcementAction.ALLOW:
        print("  ✅ Request ALLOWED - Under budget")

    print()

    # Step 5: Custom callback example
    print("Step 5: Custom callback example")
    print("-" * 70)

    def custom_callback(context):
        """Custom callback: Block GPT-4 for free tier."""
        if context.user_tier == "free" and context.model == "gpt-4":
            return EnforcementAction.BLOCK
        return EnforcementAction.ALLOW

    custom_callbacks = EnforcementCallbacks()
    custom_callbacks.register(custom_callback)

    # Test with GPT-4
    context = EnforcementContext(
        user_id="free_user_001",
        user_tier="free",
        model="gpt-4",
        budget_exceeded=False,
    )

    action = custom_callbacks.check(context)
    print(f"  Free user requesting GPT-4 → Action: {action.value.upper()}")

    # Test with GPT-4o-mini
    context.model = "gpt-4o-mini"  # Updated from deprecated gpt-3.5-turbo
    action = custom_callbacks.check(context)
    print(f"  Free user requesting GPT-4o-mini → Action: {action.value.upper()}")

    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print("Built-in callbacks available:")
    print("  - strict_budget_enforcement: Block at 100%, warn at 80%")
    print("  - graceful_degradation: Degrade at 90%, block at 100%")
    print("  - tier_based_enforcement: Different policies per tier")
    print()
    print("Custom callbacks: Define your own business logic")
    print("=" * 70)


if __name__ == "__main__":
    main()
