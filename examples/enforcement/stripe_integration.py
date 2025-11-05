"""
Stripe Integration Example

Demonstrates integrating cascadeflow enforcement with Stripe subscriptions.

This is a TEMPLATE - requires actual Stripe API credentials to run.

Shows:
- Mapping Stripe subscription tiers to budgets
- Checking user tier from Stripe
- Budget enforcement based on subscription
- Handling budget exceeded → upgrade flow
"""

from cascadeflow.telemetry import (
    BudgetConfig,
    CostTracker,
    EnforcementAction,
    EnforcementCallbacks,
    EnforcementContext,
    tier_based_enforcement,
)

# NOTE: This is a template - you'll need to install stripe:
# pip install stripe
#
# import stripe
# stripe.api_key = "sk_test_..."


# Stripe price IDs (from your Stripe dashboard)
STRIPE_TIERS = {
    "price_free": {
        "name": "free",
        "budget": BudgetConfig(daily=0.10),
        "monthly_price": 0,
    },
    "price_pro": {
        "name": "pro",
        "budget": BudgetConfig(daily=1.0, weekly=5.0, monthly=20.0),
        "monthly_price": 29,
    },
    "price_enterprise": {
        "name": "enterprise",
        "budget": BudgetConfig(daily=50.0, monthly=1000.0),
        "monthly_price": 499,
    },
}


def get_user_tier_from_stripe(user_id: str) -> dict:
    """
    Get user's subscription tier from Stripe.

    In production, this would call Stripe API:
    subscription = stripe.Subscription.retrieve(user_subscription_id)
    price_id = subscription["items"]["data"][0]["price"]["id"]
    return STRIPE_TIERS[price_id]

    For demo purposes, we'll simulate it.
    """
    # Simulated - in production, call Stripe API
    simulated_tiers = {
        "user_free_001": "price_free",
        "user_pro_001": "price_pro",
        "user_ent_001": "price_enterprise",
    }

    price_id = simulated_tiers.get(user_id, "price_free")
    return STRIPE_TIERS[price_id]


def main():
    print("=" * 70)
    print("Stripe Integration Example (TEMPLATE)")
    print("=" * 70)
    print()
    print("NOTE: This is a template. In production, integrate with Stripe API.")
    print()

    # Step 1: Configure cost tracker with Stripe-based budgets
    print("Step 1: Configure budgets from Stripe tiers")
    print("-" * 70)

    # Extract budgets from Stripe tier config
    user_budgets = {tier["name"]: tier["budget"] for tier in STRIPE_TIERS.values()}

    tracker = CostTracker(user_budgets=user_budgets, verbose=True)

    print(f"✓ Configured {len(user_budgets)} tiers from Stripe:")
    for tier_name, budget_config in user_budgets.items():
        print(f"  - {tier_name}: {budget_config}")
    print()

    # Step 2: Set up enforcement callbacks
    print("Step 2: Configure tier-based enforcement")
    print("-" * 70)

    callbacks = EnforcementCallbacks(verbose=True)
    callbacks.register(tier_based_enforcement)

    print("✓ Registered tier_based_enforcement callback")
    print("  - Free: Block at 100%, warn at 80%")
    print("  - Pro: Degrade at 100%, warn at 90%")
    print("  - Enterprise: Warn only (never block)")
    print()

    # Step 3: Simulate requests from different users
    print("Step 3: Process requests from users with different Stripe tiers")
    print("-" * 70)

    def process_user_request(user_id: str, query: str, estimated_cost: float):
        """Simulate processing a user request with budget enforcement."""
        # Get user's Stripe tier
        tier_info = get_user_tier_from_stripe(user_id)
        tier_name = tier_info["name"]

        # Get current user costs
        summary = tracker.get_user_summary(user_id, tier_name)

        # Build enforcement context
        context = EnforcementContext(
            user_id=user_id,
            user_tier=tier_name,
            current_cost=summary.get("total_cost", 0.0),
            estimated_cost=estimated_cost,
            budget_limit=tier_info["budget"].daily if tier_info["budget"].daily else None,
            budget_used_pct=summary.get("period_costs", {})
            .get("daily", {})
            .get("used_pct", 0.0),
            budget_exceeded=summary.get("budget_exceeded", False),
            query=query,
        )

        # Check enforcement
        action = callbacks.check(context)

        print(f"\n  User: {user_id} (Stripe tier: {tier_name})")
        print(f"  Current cost: ${context.current_cost:.4f}")
        print(f"  Budget used: {context.budget_used_pct:.1f}%")
        print(f"  Action: {action.value.upper()}")

        # Handle action
        if action == EnforcementAction.BLOCK:
            print(f"  → ⛔ BLOCKED - Upgrade required")
            print(f"     Upgrade to {get_upgrade_tier(tier_name)} for higher limits!")
            return None

        elif action == EnforcementAction.WARN:
            print(f"  → ⚠️  ALLOWED (with warning) - Approaching limit")
            # Track cost
            tracker.add_cost(
                model="gpt-4",
                provider="openai",
                tokens=1000,
                cost=estimated_cost,
                user_id=user_id,
                user_tier=tier_name,
            )
            return "Response with warning..."

        elif action == EnforcementAction.DEGRADE:
            print(f"  → ⬇️  DEGRADED - Using cheaper model")
            # Use cheaper model
            tracker.add_cost(
                model="gpt-3.5-turbo",  # Cheaper model
                provider="openai",
                tokens=1000,
                cost=estimated_cost * 0.1,  # 10x cheaper
                user_id=user_id,
                user_tier=tier_name,
            )
            return "Response from cheaper model..."

        else:  # ALLOW
            print(f"  → ✅ ALLOWED - Under budget")
            tracker.add_cost(
                model="gpt-4",
                provider="openai",
                tokens=1000,
                cost=estimated_cost,
                user_id=user_id,
                user_tier=tier_name,
            )
            return "Response..."

    # Free user - will get blocked quickly
    print("\n▶ Free user requests:")
    for i in range(4):
        process_user_request("user_free_001", f"Query {i+1}", 0.03)

    # Pro user - will get degraded
    print("\n▶ Pro user requests:")
    for i in range(15):
        process_user_request("user_pro_001", f"Query {i+1}", 0.08)

    # Enterprise user - only warned
    print("\n▶ Enterprise user requests:")
    for i in range(20):
        if i in [0, 10, 19]:  # Only show a few
            process_user_request("user_ent_001", f"Query {i+1}", 3.0)

    print()
    print("=" * 70)
    print("Integration Summary")
    print("=" * 70)
    print()
    print("Production Integration Steps:")
    print("1. Install Stripe SDK: pip install stripe")
    print("2. Set Stripe API key: stripe.api_key = 'sk_...'")
    print("3. Fetch user subscription: stripe.Subscription.retrieve(...)")
    print("4. Map subscription price_id to tier budgets")
    print("5. Use EnforcementCallbacks to enforce limits")
    print("6. Handle BLOCK → Redirect to upgrade page")
    print("7. Handle DEGRADE → Use cheaper models")
    print()
    print("Benefits:")
    print("✓ Automatic budget enforcement per Stripe tier")
    print("✓ Prevent cost overruns for free users")
    print("✓ Graceful degradation for pro users")
    print("✓ No blocking for enterprise users")
    print("=" * 70)


def get_upgrade_tier(current_tier: str) -> str:
    """Get the next upgrade tier."""
    upgrades = {"free": "Pro ($29/mo)", "pro": "Enterprise ($499/mo)"}
    return upgrades.get(current_tier, "Enterprise")


if __name__ == "__main__":
    main()
