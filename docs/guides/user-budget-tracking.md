# Per-User Budget Tracking

**NEW in v0.2.0** - Track and enforce budgets per user with automatic time-based resets.

## Overview

CascadeFlow's per-user budget tracking helps you control costs in multi-user applications by:

- **Tracking costs per user** - Separate cost tracking for each user ID
- **Enforcing tier-based budgets** - Different limits for free, pro, enterprise users
- **Multiple time periods** - Daily, weekly, monthly, and total lifetime budgets
- **Automatic resets** - Daily budgets reset after 24 hours, weekly after 7 days
- **Warning thresholds** - Get alerts when users reach 80% (configurable) of budget
- **100% backward compatible** - Existing v0.1.1 code continues to work

## Quick Start

```python
from cascadeflow.telemetry import BudgetConfig, CostTracker

# Configure tier-based budgets
tracker = CostTracker(
    user_budgets={
        "free": BudgetConfig(daily=0.10),  # $0.10/day for free users
        "pro": BudgetConfig(daily=1.0, weekly=5.0),  # $1/day, $5/week
    },
    warn_threshold=0.8,  # Warn at 80% of budget
)

# Track costs with user context
tracker.add_cost(
    model="gpt-4",
    provider="openai",
    tokens=1000,
    cost=0.003,
    user_id="user_123",
    user_tier="free",
)

# Check user's budget status
summary = tracker.get_user_summary("user_123", "free")
if summary["budget_exceeded"]:
    print("⚠️ User has exceeded their daily budget!")
```

## API Reference

### BudgetConfig

Configure budget limits for a user tier.

```python
from cascadeflow.telemetry import BudgetConfig

# Daily budget only (most common for SaaS)
free_tier = BudgetConfig(daily=0.10)

# Multiple periods for comprehensive control
pro_tier = BudgetConfig(
    daily=1.00,
    weekly=5.00,
    monthly=20.00,
)

# Total lifetime budget (for trials)
trial = BudgetConfig(total=5.00)

# No limits (tracking only)
unlimited = BudgetConfig()  # No enforcement, just tracking
```

**Parameters:**
- `daily` (float, optional): Daily budget in USD (resets every 24 hours)
- `weekly` (float, optional): Weekly budget in USD (resets every 7 days)
- `monthly` (float, optional): Monthly budget in USD (resets every 30 days)
- `total` (float, optional): Total lifetime budget in USD (never resets)

### CostTracker with User Budgets

```python
from cascadeflow.telemetry import BudgetConfig, CostTracker

tracker = CostTracker(
    budget_limit=100.0,  # Optional global budget (v0.1.1 - backward compatible)
    user_budgets={       # NEW in v0.2.0
        "free": BudgetConfig(daily=0.10),
        "pro": BudgetConfig(daily=1.0, weekly=5.0),
        "enterprise": BudgetConfig(daily=10.0, monthly=200.0),
    },
    warn_threshold=0.8,  # Warn at 80% of budget
    verbose=True,        # Enable logging
)
```

### add_cost() with User Tracking

```python
# v0.2.0 style - with user tracking
tracker.add_cost(
    model="gpt-4",
    provider="openai",
    tokens=1000,
    cost=0.003,
    user_id="user_123",      # NEW: User identifier
    user_tier="free",        # NEW: User tier name
    query_id="query_456",    # Optional
    metadata={"app": "web"}, # Optional
)

# v0.1.1 style - still works (no user tracking)
tracker.add_cost(
    model="gpt-4",
    provider="openai",
    tokens=1000,
    cost=0.003,
)
```

### get_user_summary()

Get detailed cost summary for a specific user.

```python
summary = tracker.get_user_summary("user_123", "free")

# Summary structure:
{
    "user_id": "user_123",
    "total_cost": 0.045,  # Total cost across all time
    "total_entries": 3,   # Number of queries
    "user_tier": "free",
    "budget_config": "BudgetConfig(daily=$0.10)",
    "period_costs": {
        "daily": {
            "cost": 0.045,
            "limit": 0.10,
            "remaining": 0.055,
            "used_pct": 45.0,
            "exceeded": False,
        }
    },
    "budget_exceeded": False,  # True if ANY period exceeded
}
```

### get_all_users()

Get list of all tracked user IDs.

```python
users = tracker.get_all_users()
# Returns: ["user_123", "user_456", "user_789"]
```

### get_users_by_tier()

Get all users in a specific tier.

```python
free_users = tracker.get_users_by_tier("free")
# Returns: ["user_123", "user_456"]
```

## Real-World Scenarios

### Scenario 1: SaaS with Free and Pro Tiers

```python
from cascadeflow.telemetry import BudgetConfig, CostTracker

# Configure budgets
tracker = CostTracker(
    user_budgets={
        "free": BudgetConfig(daily=0.10),
        "pro": BudgetConfig(daily=1.0, weekly=5.0, monthly=20.0),
    },
    warn_threshold=0.8,
)

# Process user query
def process_query(user_id, user_tier, query):
    # ... run query through CascadeFlow ...

    # Track cost
    tracker.add_cost(
        model="gpt-4",
        provider="openai",
        tokens=tokens_used,
        cost=calculated_cost,
        user_id=user_id,
        user_tier=user_tier,
    )

    # Check if budget exceeded
    summary = tracker.get_user_summary(user_id, user_tier)
    if summary["budget_exceeded"]:
        # Deny request or show upgrade prompt
        return {"error": "Daily budget exceeded. Please upgrade to Pro!"}

    return result
```

### Scenario 2: Trial Users with Lifetime Budget

```python
# Trial users get $5 total budget
tracker = CostTracker(
    user_budgets={
        "trial": BudgetConfig(total=5.0),
    }
)

# Track trial user
tracker.add_cost(
    model="gpt-4",
    provider="openai",
    tokens=1000,
    cost=0.60,
    user_id="trial_user_001",
    user_tier="trial",
)

# Check remaining budget
summary = tracker.get_user_summary("trial_user_001", "trial")
remaining = summary["period_costs"]["total"]["remaining"]
print(f"Trial budget remaining: ${remaining:.2f}")
```

### Scenario 3: Enterprise with Monthly Budget

```python
# Enterprise gets high daily limit but capped monthly
tracker = CostTracker(
    user_budgets={
        "enterprise": BudgetConfig(daily=50.0, monthly=1000.0),
    }
)

# Track enterprise user
tracker.add_cost(
    model="gpt-4",
    provider="openai",
    tokens=10000,
    cost=5.0,
    user_id="enterprise_user_001",
    user_tier="enterprise",
)

# Monthly budget tracking
summary = tracker.get_user_summary("enterprise_user_001", "enterprise")
monthly = summary["period_costs"]["monthly"]
print(f"Monthly usage: ${monthly['cost']:.2f} / ${monthly['limit']:.2f}")
```

## Time-Based Resets

Budgets automatically reset based on the time period:

| Period | Reset Frequency | Example |
|--------|----------------|---------|
| Daily | Every 24 hours | User spent $0.10 on Monday, budget resets to $0 on Tuesday |
| Weekly | Every 7 days | Week starts on Monday, resets the following Monday |
| Monthly | Every 30 days | 30-day rolling window |
| Total | Never | Lifetime cumulative budget |

**Note:** Resets happen automatically when checking budgets. If a user makes their first query on Tuesday at 3pm, their daily budget runs until Wednesday at 3pm.

## Warning Thresholds

Configure when to warn users about budget usage:

```python
tracker = CostTracker(
    user_budgets={"free": BudgetConfig(daily=0.10)},
    warn_threshold=0.8,  # Warn at 80%
)

# When user reaches 80% of $0.10 ($0.08), you'll see:
# WARNING: User user_123 (free): 80.0% of daily budget used ($0.080 / $0.10)
```

You can listen to these warnings by enabling verbose logging:

```python
import logging
logging.basicConfig(level=logging.WARNING)

tracker = CostTracker(
    user_budgets={"free": BudgetConfig(daily=0.10)},
    warn_threshold=0.8,
    verbose=True,  # Enable logging
)
```

## Performance

Per-user budget tracking is designed for production use:

- **<1ms overhead** per `add_cost()` call (measured with 100 calls)
- **O(users)** memory complexity
- **Thread-safe** - uses only atomic operations
- **Minimal CPU** - simple dict lookups and comparisons

Benchmark on MacBook Pro:
```
1000 users × 10 queries each = 10,000 add_cost() calls
Total time: ~8ms
Average per call: 0.8ms
```

## Integration with Auth Systems

### With Stripe

```python
import stripe
from cascadeflow.telemetry import BudgetConfig, CostTracker

# Map Stripe subscription tiers to budgets
TIER_BUDGETS = {
    "price_free": BudgetConfig(daily=0.10),
    "price_pro": BudgetConfig(daily=1.0, weekly=5.0),
    "price_enterprise": BudgetConfig(daily=50.0, monthly=1000.0),
}

tracker = CostTracker(user_budgets=TIER_BUDGETS)

# Get user's Stripe subscription
subscription = stripe.Subscription.retrieve(user_subscription_id)
price_id = subscription["items"]["data"][0]["price"]["id"]

# Track with Stripe price ID as tier
tracker.add_cost(
    model="gpt-4",
    provider="openai",
    tokens=1000,
    cost=0.003,
    user_id=user.id,
    user_tier=price_id,  # Use Stripe price ID
)
```

### With Auth0

```python
from cascadeflow.telemetry import BudgetConfig, CostTracker

# Map Auth0 roles to budgets
ROLE_BUDGETS = {
    "free-user": BudgetConfig(daily=0.10),
    "pro-user": BudgetConfig(daily=1.0, weekly=5.0),
    "enterprise-user": BudgetConfig(daily=50.0, monthly=1000.0),
}

tracker = CostTracker(user_budgets=ROLE_BUDGETS)

# Get user's Auth0 role
user_roles = auth0_user["app_metadata"]["roles"]
tier = user_roles[0]  # Primary role

# Track with Auth0 role
tracker.add_cost(
    model="gpt-4",
    provider="openai",
    tokens=1000,
    cost=0.003,
    user_id=auth0_user["user_id"],
    user_tier=tier,
)
```

## Best Practices

### 1. Define Clear Tier Budgets

```python
# Good: Clear tier budgets
TIER_BUDGETS = {
    "free": BudgetConfig(daily=0.10),         # 10 cents/day
    "pro": BudgetConfig(daily=1.0, weekly=5.0), # $1/day, $5/week
    "enterprise": BudgetConfig(monthly=1000.0), # $1000/month only
}

# Bad: Overly complex
TIER_BUDGETS = {
    "free": BudgetConfig(daily=0.10, weekly=0.50, monthly=2.0, total=10.0),
    # Too many periods - hard to explain to users
}
```

### 2. Use Appropriate Periods

```python
# For SaaS: Daily budgets (easy to understand)
BudgetConfig(daily=0.10)

# For trials: Total budgets (fixed lifetime)
BudgetConfig(total=5.0)

# For enterprise: Monthly budgets (matches billing cycle)
BudgetConfig(monthly=1000.0)
```

### 3. Handle Budget Exceeded Gracefully

```python
def handle_query(user_id, user_tier, query):
    summary = tracker.get_user_summary(user_id, user_tier)

    if summary.get("budget_exceeded"):
        # Show friendly message
        if user_tier == "free":
            return {
                "error": "Daily budget exceeded",
                "message": "Upgrade to Pro for higher limits!",
                "upgrade_url": "/upgrade",
            }
        else:
            return {
                "error": "Budget limit reached",
                "message": "Contact sales to increase your limit.",
                "support_email": "sales@example.com",
            }

    # Process query normally
    return process_query(query)
```

### 4. Monitor Budget Usage

```python
# Periodic monitoring (e.g., daily cron job)
def monitor_budget_usage():
    all_users = tracker.get_all_users()

    for user_id in all_users:
        summary = tracker.get_user_summary(user_id)

        # Send warning email if close to limit
        if summary.get("period_costs", {}).get("daily", {}).get("used_pct", 0) > 90:
            send_email(
                user_id,
                subject="Budget Warning",
                body=f"You've used {summary['period_costs']['daily']['used_pct']:.0f}% of your daily budget"
            )
```

### 5. Track Without Enforcement (Optional)

```python
# Track costs but don't enforce limits (analytics only)
tracker = CostTracker()  # No user_budgets

tracker.add_cost(
    model="gpt-4",
    provider="openai",
    tokens=1000,
    cost=0.003,
    user_id="user_123",
    # No user_tier - just tracking
)

# Still get cost breakdown
summary = tracker.get_user_summary("user_123")
print(f"User has spent: ${summary['total_cost']:.2f}")
```

## Backward Compatibility

All v0.1.1 code continues to work without modification:

```python
# v0.1.1 style - still works
tracker = CostTracker(budget_limit=10.0)
tracker.add_cost(model="gpt-4", provider="openai", tokens=100, cost=0.003)
summary = tracker.get_summary()

# v0.2.0 adds optional user tracking
tracker.add_cost(
    model="gpt-4",
    provider="openai",
    tokens=100,
    cost=0.003,
    user_id="user_123",  # Optional - if omitted, no user tracking
    user_tier="free",    # Optional
)
```

## Next Steps

- [Production Deployment Guide](production.md) - Deploy with user tracking
- [Cost Optimization](cost-optimization.md) - Reduce costs with cascading
- [API Reference](../api/telemetry.md) - Full telemetry API docs
- [Examples](../../examples/user_budget_tracking.py) - Complete working example

## Troubleshooting

### Budget not resetting

**Problem:** Daily budget shows same cost after 24 hours

**Solution:** Budgets reset automatically when `add_cost()` is called. If a user doesn't make any queries, the reset won't happen until their next query.

```python
# Budget resets happen in add_cost() when checking if period expired
tracker.add_cost(...)  # This triggers reset check
```

### User not found

**Problem:** `get_user_summary()` returns `total_cost: 0.0` for existing user

**Solution:** Make sure you're using the exact same `user_id` string:

```python
# Good
tracker.add_cost(..., user_id="user_123", user_tier="free")
summary = tracker.get_user_summary("user_123", "free")  # Same ID

# Bad
tracker.add_cost(..., user_id="user_123", user_tier="free")
summary = tracker.get_user_summary("user-123", "free")  # Different ID (dash vs underscore)
```

### Budget exceeded not triggering

**Problem:** Budget shows exceeded but no warning/error logged

**Solution:** Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.WARNING)

tracker = CostTracker(
    user_budgets={"free": BudgetConfig(daily=0.10)},
    verbose=True,  # Must be True to see logs
)
```

Or check the `budget_exceeded` flag programmatically:

```python
summary = tracker.get_user_summary(user_id, user_tier)
if summary.get("budget_exceeded"):
    # Handle exceeded budget
    pass
```
