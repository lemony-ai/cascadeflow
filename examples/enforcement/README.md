# Budget Enforcement Examples

Production-ready examples for implementing budget enforcement and cost controls with cascadeflow.

## 📋 Table of Contents

- [Basic Enforcement](#-basic-enforcement) - Budget limits and enforcement callbacks
- [Stripe Integration](#-stripe-integration) - Real-world SaaS integration template

---

## 🛡️ Basic Enforcement

**File:** [`basic_enforcement.py`](basic_enforcement.py)

Learn how to implement budget enforcement with built-in and custom callbacks.

### Quick Start

```bash
# Run the example (no API keys required)
python examples/enforcement/basic_enforcement.py
```

### What It Demonstrates

1. **Configure Budget Limits** - Set daily/weekly/monthly budgets per tier
2. **Built-in Callbacks** - Use pre-built enforcement policies
3. **Custom Callbacks** - Create your own enforcement logic
4. **Action Handling** - ALLOW, WARN, BLOCK, or DEGRADE requests

### Example Output

```
Step 3: Simulate free user making requests
----------------------------------------------------------------------
  Query 1: Cost=$0.05, Used=50% → Action: ALLOW
  Query 2: Cost=$0.085, Used=85% → Action: WARN
  Query 3: Cost=$0.105, Used=105% → Action: BLOCK

Step 4: Handle enforcement action in application
----------------------------------------------------------------------
  ⛔ Request BLOCKED - User exceeded daily budget
  → Show upgrade prompt to user
```

### Usage Example

```python
from cascadeflow.telemetry import (
    BudgetConfig,
    CostTracker,
    EnforcementCallbacks,
    EnforcementContext,
    strict_budget_enforcement,
)

# Step 1: Configure budgets per tier
tracker = CostTracker(
    user_budgets={
        "free": BudgetConfig(daily=0.10),
        "pro": BudgetConfig(daily=1.0),
        "enterprise": BudgetConfig(daily=50.0),
    }
)

# Step 2: Set up enforcement callbacks
callbacks = EnforcementCallbacks()
callbacks.register(strict_budget_enforcement)

# Step 3: Track costs
tracker.add_cost(
    model="gpt-4o-mini",
    provider="openai",
    tokens=500,
    cost=0.05,
    user_id="user_123",
    user_tier="free",
)

# Step 4: Check enforcement before processing request
context = EnforcementContext(
    user_id="user_123",
    user_tier="free",
    current_cost=0.05,
    budget_limit=0.10,
    budget_used_pct=50.0,
    budget_exceeded=False,
)

action = callbacks.check(context)

# Step 5: Handle action
if action == EnforcementAction.BLOCK:
    return {"error": "Budget exceeded. Please upgrade."}
elif action == EnforcementAction.WARN:
    # Log warning but allow request
    logger.warning(f"User {user_id} approaching budget limit")
```

### Built-in Callbacks

**1. strict_budget_enforcement**
- Block at 100% of budget
- Warn at 80% of budget
- Best for: Free tiers, strict cost control

**2. graceful_degradation**
- Degrade to cheaper models at 90%
- Block at 100%
- Best for: Pro tiers, quality/cost balance

**3. tier_based_enforcement**
- Free: Block at 100%, warn at 80%
- Pro: Degrade at 100%, warn at 90%
- Enterprise: Warn only (never block)
- Best for: Multi-tier SaaS applications

### Custom Callbacks

Create your own enforcement logic:

```python
def custom_callback(context):
    """Block expensive models for free tier."""
    if context.user_tier == "free" and context.model in ["gpt-4", "gpt-4o"]:
        return EnforcementAction.BLOCK
    return EnforcementAction.ALLOW

callbacks.register(custom_callback)
```

---

## 💳 Stripe Integration

**File:** [`stripe_integration.py`](stripe_integration.py)

Template for integrating cascadeflow enforcement with Stripe subscriptions.

### Quick Start

```bash
# Run the template (simulates Stripe integration)
python examples/enforcement/stripe_integration.py
```

**Note:** This is a template. To use in production, install Stripe SDK and add your API keys.

### What It Demonstrates

1. **Stripe Tier Mapping** - Map Stripe price IDs to budget configs
2. **Subscription-based Budgets** - Different limits per subscription tier
3. **Tier-based Enforcement** - Apply different policies per tier
4. **Upgrade Flow** - Handle budget exceeded → upgrade prompts

### Stripe Tier Configuration

```python
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
```

### Production Integration Steps

```python
# 1. Install Stripe SDK
pip install stripe

# 2. Configure Stripe
import stripe
stripe.api_key = "sk_live_..."

# 3. Get user subscription
subscription = stripe.Subscription.retrieve(user_subscription_id)
price_id = subscription["items"]["data"][0]["price"]["id"]

# 4. Map to budget tier
tier_info = STRIPE_TIERS[price_id]

# 5. Configure enforcement
tracker = CostTracker(
    user_budgets={tier["name"]: tier["budget"] for tier in STRIPE_TIERS.values()}
)

callbacks = EnforcementCallbacks()
callbacks.register(tier_based_enforcement)

# 6. Check before processing
context = EnforcementContext(
    user_id=user_id,
    user_tier=tier_info["name"],
    current_cost=tracker.get_user_cost(user_id),
    budget_limit=tier_info["budget"].daily,
    budget_exceeded=tracker.is_budget_exceeded(user_id),
)

action = callbacks.check(context)

# 7. Handle enforcement
if action == EnforcementAction.BLOCK:
    # Redirect to upgrade page
    return redirect(f"/upgrade?from={tier_info['name']}")
elif action == EnforcementAction.DEGRADE:
    # Use cheaper model
    model = "gpt-4o-mini"  # Instead of gpt-4o
```

### Example Flow

```
Free User ($0 - $0.10/day):
  Request 1: $0.03 → ✅ ALLOWED (30% used)
  Request 2: $0.06 → ⚠️ WARNED (60% used)
  Request 3: $0.09 → ⚠️ WARNED (90% used)
  Request 4: $0.12 → ⛔ BLOCKED → Upgrade prompt

Pro User ($29/mo - $1.00/day):
  Requests 1-10: ✅ ALLOWED
  Requests 11-12: ⚠️ WARNED (approaching limit)
  Request 13: ⬇️ DEGRADED (use cheaper model)
  Request 14: ⬇️ DEGRADED (continue with cheap model)

Enterprise User ($499/mo - $50/day):
  Requests 1-100: ✅ ALLOWED
  High usage: ⚠️ WARNED (monitoring only, never blocked)
```

---

## 📁 Files Overview

| File | Purpose | API Keys Required |
|------|---------|-------------------|
| `basic_enforcement.py` | Learn enforcement callbacks and actions | No |
| `stripe_integration.py` | Stripe subscription integration template | No (for demo) |

---

## 🎯 Use Cases

### 1. SaaS Free Tier
**Goal:** Prevent free users from exceeding budget

```python
tracker = CostTracker(
    user_budgets={"free": BudgetConfig(daily=0.10)}
)
callbacks = EnforcementCallbacks()
callbacks.register(strict_budget_enforcement)
```

**Result:**
- Warn at 80% ($0.08)
- Block at 100% ($0.10)
- Show upgrade prompt when blocked

### 2. Multi-Tier SaaS
**Goal:** Different policies per subscription tier

```python
tracker = CostTracker(
    user_budgets={
        "free": BudgetConfig(daily=0.10),
        "pro": BudgetConfig(daily=1.0),
        "enterprise": BudgetConfig(daily=50.0),
    }
)
callbacks = EnforcementCallbacks()
callbacks.register(tier_based_enforcement)
```

**Result:**
- Free: Strict blocking
- Pro: Graceful degradation
- Enterprise: Monitoring only

### 3. Custom Business Logic
**Goal:** Enforce specific model access per tier

```python
def model_access_control(context):
    """Block expensive models for free tier."""
    expensive_models = ["gpt-4", "gpt-4o", "claude-3-opus"]

    if context.user_tier == "free" and context.model in expensive_models:
        return EnforcementAction.BLOCK
    return EnforcementAction.ALLOW

callbacks.register(model_access_control)
```

**Result:**
- Free users can only use gpt-4o-mini, claude-3-haiku
- Pro/Enterprise can use any model

### 4. Cost Overrun Prevention
**Goal:** Never exceed infrastructure budget

```python
# Set hard cap at infrastructure level
tracker = CostTracker(
    user_budgets={"default": BudgetConfig(monthly=5000.0)}
)

def infrastructure_cap(context):
    """Block all requests if monthly budget exceeded."""
    if context.budget_exceeded:
        return EnforcementAction.BLOCK
    return EnforcementAction.ALLOW

callbacks.register(infrastructure_cap)
```

**Result:**
- System-wide protection against runaway costs
- All requests blocked when monthly cap reached

---

## 🔧 Enforcement Actions

### ALLOW ✅
Request proceeds normally with premium model.

```python
if action == EnforcementAction.ALLOW:
    result = await agent.run(query, model="gpt-4o")
    return result
```

### WARN ⚠️
Request proceeds but log warning for monitoring.

```python
if action == EnforcementAction.WARN:
    logger.warning(f"User {user_id} at {budget_used}% budget")
    result = await agent.run(query, model="gpt-4o")
    return result
```

### DEGRADE ⬇️
Request proceeds with cheaper model.

```python
if action == EnforcementAction.DEGRADE:
    result = await agent.run(query, model="gpt-4o-mini")  # Cheaper
    return result
```

### BLOCK ⛔
Request rejected, show upgrade prompt.

```python
if action == EnforcementAction.BLOCK:
    return {
        "error": "Budget exceeded",
        "message": "Upgrade to continue using AI features",
        "upgrade_url": "/upgrade"
    }
```

---

## 🚀 Production Best Practices

### 1. Check Before Processing

```python
# ALWAYS check enforcement before making API call
action = callbacks.check(context)

if action == EnforcementAction.BLOCK:
    return error_response()

# Only proceed if allowed/warned/degraded
result = await process_request()
```

### 2. Track Costs Accurately

```python
# Track actual API costs, not estimates
result = await agent.run(query)

tracker.add_cost(
    model=result.model_used,
    provider=result.provider,
    tokens=result.metadata["total_tokens"],
    cost=result.total_cost,  # Actual cost from API
    user_id=user_id,
    user_tier=user_tier,
)
```

### 3. Handle All Actions

```python
action = callbacks.check(context)

if action == EnforcementAction.BLOCK:
    return handle_block(user_id)
elif action == EnforcementAction.DEGRADE:
    return handle_degradation(query)
elif action == EnforcementAction.WARN:
    logger.warning(f"User {user_id} approaching limit")
    return handle_normal(query)
else:  # ALLOW
    return handle_normal(query)
```

### 4. Sync with Billing System

```python
# Periodically sync budgets with billing system
def sync_user_budget(user_id):
    """Sync budget from Stripe/billing system."""
    subscription = get_user_subscription(user_id)
    tier_info = STRIPE_TIERS[subscription.price_id]

    # Update tracker with latest budget
    tracker.update_user_budget(user_id, tier_info["budget"])
```

### 5. Monitor and Alert

```python
# Set up monitoring for budget events
callbacks.on_warn = lambda ctx: alert_ops(f"User {ctx.user_id} at {ctx.budget_used_pct}%")
callbacks.on_block = lambda ctx: log_block_event(ctx.user_id)
```

---

## 🔍 Troubleshooting

### Users getting blocked unexpectedly

**Check budget configuration:**
```python
summary = tracker.get_user_summary(user_id, user_tier)
print(f"Budget used: {summary['period_costs']['daily']['used_pct']:.1f}%")
print(f"Budget limit: ${summary['budget_limit']}")
```

### Budget not resetting

Budgets reset automatically based on period:
- Daily: Resets at midnight UTC
- Weekly: Resets on Monday 00:00 UTC
- Monthly: Resets on 1st of month 00:00 UTC

**Check current period:**
```python
tracker.get_period_costs(user_id, "daily")
```

### Enforcement not working

**Verify callback is registered:**
```python
callbacks = EnforcementCallbacks(verbose=True)  # Enable logging
callbacks.register(strict_budget_enforcement)

# Check if callback is called
action = callbacks.check(context)
print(f"Action: {action}")
```

---

## 📚 Related Documentation

- **Cost Tracking:** [examples/cost_tracking.py](../cost_tracking.py)
- **Cost Guide:** [docs/guides/cost_tracking.md](../../docs/guides/cost_tracking.md)
- **Production Guide:** [docs/guides/production.md](../../docs/guides/production.md)

---

## 🚀 Next Steps

1. **Try basic enforcement:** `python examples/enforcement/basic_enforcement.py`
2. **Review Stripe template:** `python examples/enforcement/stripe_integration.py`
3. **Implement in your app:** Use code snippets above
4. **Add monitoring:** Track WARN and BLOCK events
5. **Test edge cases:** Users switching tiers, multiple periods, etc.

---

**🛡️ Protect your AI costs with production-ready enforcement!** 🚀
