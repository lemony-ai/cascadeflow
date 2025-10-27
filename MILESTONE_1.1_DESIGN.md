# Milestone 1.1: Per-User Budget Tracking - Design Document

**Phase:** 1 (Cost Control Foundation)
**Week:** 1
**Status:** Design Phase - Awaiting Validation
**Date:** 2025-10-27

---

## 🎯 Goal

Add per-user cost tracking and budget management to CascadeFlow, enabling SaaS applications to enforce budgets for different user tiers (free, pro, enterprise).

---

## 📋 Success Criteria

### Functional Requirements
1. ✅ Track costs per user ID
2. ✅ Support multiple budget periods (daily, weekly, monthly, total)
3. ✅ Maintain backward compatibility (existing CostTracker usage still works)
4. ✅ Per-user budget warnings and alerts
5. ✅ Per-user cost summaries
6. ✅ 100% test coverage for new functionality

### Real-World Benefit Validation
1. ✅ Sarah's SaaS can enforce free tier budget ($0.10/day per user)
2. ✅ Easy integration with existing user systems (Stripe, Auth0, etc.)
3. ✅ Zero performance overhead (<1ms per add_cost call)
4. ✅ Simple API (developer can understand in 5 minutes)

### Production Readiness
1. ✅ Thread-safe (if used in async contexts)
2. ✅ Memory efficient (O(users) space, not O(queries))
3. ✅ Clear error messages
4. ✅ Graceful handling of missing/invalid user IDs

---

## 🏗️ API Design

### New Classes

#### `BudgetConfig` Dataclass

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class BudgetConfig:
    """
    Per-user budget configuration.

    Supports multiple budget periods. Only specify the periods you need.
    If no budget is specified, tracking still happens but no limits enforced.

    Examples:
        >>> # Daily budget only (most common for SaaS)
        >>> free_tier = BudgetConfig(daily=0.10)
        >>>
        >>> # Multiple periods
        >>> pro_tier = BudgetConfig(
        ...     daily=1.00,
        ...     weekly=5.00,
        ...     monthly=20.00
        ... )
        >>>
        >>> # Total lifetime budget
        >>> trial = BudgetConfig(total=5.00)
    """

    daily: Optional[float] = None      # Daily budget in USD
    weekly: Optional[float] = None     # Weekly budget in USD
    monthly: Optional[float] = None    # Monthly budget in USD
    total: Optional[float] = None      # Total lifetime budget in USD

    def has_any_limit(self) -> bool:
        """Check if any budget limit is set."""
        return any([self.daily, self.weekly, self.monthly, self.total])

    def __repr__(self) -> str:
        """Human-readable representation."""
        limits = []
        if self.daily: limits.append(f"daily=${self.daily:.2f}")
        if self.weekly: limits.append(f"weekly=${self.weekly:.2f}")
        if self.monthly: limits.append(f"monthly=${self.monthly:.2f}")
        if self.total: limits.append(f"total=${self.total:.2f}")

        if not limits:
            return "BudgetConfig(no limits)"
        return f"BudgetConfig({', '.join(limits)})"
```

**Design Decisions:**
- ✅ Dataclass for immutability and clarity
- ✅ All optional (flexible for different use cases)
- ✅ Multiple periods (daily for SaaS, total for trials, etc.)
- ✅ Simple units (USD, not cents or other currencies)
- ✅ Clear repr for debugging

### Enhanced `CostTracker` Class

```python
class CostTracker:
    """
    Track costs across queries and users.

    NEW in v0.2.0: Per-user budget tracking and enforcement.

    Features (v0.1.1):
    - Per-model cost tracking ✅
    - Per-provider cost tracking ✅
    - Budget alerts ✅
    - Cost history ✅

    Features (v0.2.0 - NEW):
    - Per-user cost tracking ✅
    - Per-user budgets (daily/weekly/monthly/total) ✅
    - Per-user budget alerts ✅
    - Per-user cost summaries ✅

    Usage (v0.1.1 - Still works):
        >>> tracker = CostTracker(budget_limit=10.0)
        >>> tracker.add_cost(model='gpt-4', provider='openai',
        ...                  tokens=100, cost=0.003)

    Usage (v0.2.0 - Per-user):
        >>> # Configure per-user budgets
        >>> tracker = CostTracker(
        ...     user_budgets={
        ...         'free': BudgetConfig(daily=0.10),
        ...         'pro': BudgetConfig(daily=1.00),
        ...     }
        ... )
        >>>
        >>> # Track with user ID
        >>> tracker.add_cost(
        ...     model='gpt-4',
        ...     provider='openai',
        ...     tokens=100,
        ...     cost=0.003,
        ...     user_id='user_123',
        ...     user_tier='free'  # Used to lookup budget
        ... )
        >>>
        >>> # Get per-user summary
        >>> summary = tracker.get_user_summary('user_123')
        >>> print(f"User cost: ${summary['total_cost']:.6f}")
        >>> print(f"Budget remaining: ${summary['budget_remaining']:.6f}")
    """

    def __init__(
        self,
        budget_limit: Optional[float] = None,          # EXISTING
        warn_threshold: float = 0.8,                   # EXISTING
        verbose: bool = False,                         # EXISTING
        user_budgets: Optional[dict[str, BudgetConfig]] = None,  # NEW
    ):
        """
        Initialize cost tracker.

        Args:
            budget_limit: Optional global budget limit (v0.1.1 compatibility)
            warn_threshold: Warn when cost reaches this % of budget
            verbose: Enable verbose logging
            user_budgets: NEW - Per-user/tier budget configuration
                          Keys can be user IDs or tier names (e.g., 'free', 'pro')

        Examples:
            >>> # Global budget only (v0.1.1 style)
            >>> tracker = CostTracker(budget_limit=10.0)
            >>>
            >>> # Per-tier budgets (v0.2.0)
            >>> tracker = CostTracker(user_budgets={
            ...     'free': BudgetConfig(daily=0.10),
            ...     'pro': BudgetConfig(daily=1.00),
            ...     'enterprise': BudgetConfig(daily=10.00),
            ... })
            >>>
            >>> # Per-user budgets (v0.2.0)
            >>> tracker = CostTracker(user_budgets={
            ...     'user_123': BudgetConfig(daily=0.50),
            ...     'user_456': BudgetConfig(daily=2.00),
            ... })
            >>>
            >>> # Both global and per-user (v0.2.0)
            >>> tracker = CostTracker(
            ...     budget_limit=100.0,  # Global limit
            ...     user_budgets={'free': BudgetConfig(daily=0.10)}  # Per-tier
            ... )
        """
        # EXISTING initialization (v0.1.1)
        self.budget_limit = budget_limit
        self.warn_threshold = warn_threshold
        self.verbose = verbose

        # EXISTING tracking (v0.1.1)
        self.total_cost = 0.0
        self.by_model: dict[str, float] = defaultdict(float)
        self.by_provider: dict[str, float] = defaultdict(float)
        self.entries: list[CostEntry] = []

        # EXISTING budget alerts (v0.1.1)
        self.budget_warned = False
        self.budget_exceeded = False

        # NEW: Per-user tracking (v0.2.0)
        self.user_budgets = user_budgets or {}
        self.by_user: dict[str, float] = defaultdict(float)
        self.user_entries: dict[str, list[CostEntry]] = defaultdict(list)
        self.user_budget_warned: dict[str, bool] = defaultdict(bool)
        self.user_budget_exceeded: dict[str, bool] = defaultdict(bool)

        logger.info(
            f"CostTracker initialized: "
            f"global_budget=${budget_limit if budget_limit else 'None'}, "
            f"user_budgets={len(self.user_budgets)} configured"
        )

    def add_cost(
        self,
        model: str,
        provider: str,
        tokens: int,
        cost: float,
        query_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,      # NEW
        user_tier: Optional[str] = None,    # NEW
    ) -> None:
        """
        Add a cost entry.

        Args:
            model: Model name
            provider: Provider name
            tokens: Number of tokens used
            cost: Cost in dollars
            query_id: Optional query identifier
            metadata: Optional additional metadata
            user_id: NEW - User ID for per-user tracking
            user_tier: NEW - User tier (e.g., 'free', 'pro') for budget lookup

        Examples:
            >>> # Without user tracking (v0.1.1 style - still works)
            >>> tracker.add_cost('gpt-4', 'openai', 100, 0.003)
            >>>
            >>> # With user ID (v0.2.0)
            >>> tracker.add_cost('gpt-4', 'openai', 100, 0.003,
            ...                  user_id='user_123')
            >>>
            >>> # With user tier for budget lookup (v0.2.0)
            >>> tracker.add_cost('gpt-4', 'openai', 100, 0.003,
            ...                  user_id='user_123', user_tier='free')
        """
        # Create entry (EXISTING + user_id/user_tier in metadata)
        entry_metadata = metadata or {}
        if user_id:
            entry_metadata['user_id'] = user_id
        if user_tier:
            entry_metadata['user_tier'] = user_tier

        entry = CostEntry(
            timestamp=datetime.now(),
            model=model,
            provider=provider,
            tokens=tokens,
            cost=cost,
            query_id=query_id,
            metadata=entry_metadata,
        )

        # Update global totals (EXISTING)
        self.total_cost += cost
        self.by_model[model] += cost
        self.by_provider[provider] += cost
        self.entries.append(entry)

        # Check global budget (EXISTING)
        self._check_budget()

        # NEW: Per-user tracking
        if user_id:
            self.by_user[user_id] += cost
            self.user_entries[user_id].append(entry)
            self._check_user_budget(user_id, user_tier)

        if self.verbose:
            user_info = f", user={user_id}" if user_id else ""
            logger.info(
                f"Added cost: {model} ({provider}), "
                f"{tokens} tokens, ${cost:.6f}{user_info}"
            )

    def _check_user_budget(
        self,
        user_id: str,
        user_tier: Optional[str] = None
    ) -> None:
        """
        NEW: Check if user budget limits have been reached.

        Budget lookup order:
        1. user_budgets[user_id] (specific user budget)
        2. user_budgets[user_tier] (tier-based budget)
        3. No budget (tracking only, no enforcement)

        Args:
            user_id: User ID
            user_tier: Optional tier for budget lookup (e.g., 'free', 'pro')
        """
        # Try user-specific budget first, then tier-based
        budget = self.user_budgets.get(user_id)
        if not budget and user_tier:
            budget = self.user_budgets.get(user_tier)

        if not budget or not budget.has_any_limit():
            # No budget configured, just track
            return

        user_cost = self.by_user[user_id]

        # Check daily budget (most common)
        if budget.daily:
            # TODO: Implement time-based reset (daily/weekly/monthly)
            # For now, track against total (will add time-based in Milestone 1.2)
            usage_pct = user_cost / budget.daily

            # Warn at threshold
            if not self.user_budget_warned[user_id] and usage_pct >= self.warn_threshold:
                self.user_budget_warned[user_id] = True
                logger.warning(
                    f"User {user_id}: {usage_pct*100:.1f}% of daily budget used "
                    f"(${user_cost:.6f} / ${budget.daily:.2f})"
                )

            # Alert when exceeded
            if not self.user_budget_exceeded[user_id] and usage_pct >= 1.0:
                self.user_budget_exceeded[user_id] = True
                logger.error(
                    f"User {user_id}: Daily budget exceeded! "
                    f"${user_cost:.6f} / ${budget.daily:.2f}"
                )

        # Check total budget (if specified)
        if budget.total:
            usage_pct = user_cost / budget.total

            if not self.user_budget_warned.get(f"{user_id}_total") and usage_pct >= self.warn_threshold:
                self.user_budget_warned[f"{user_id}_total"] = True
                logger.warning(
                    f"User {user_id}: {usage_pct*100:.1f}% of total budget used "
                    f"(${user_cost:.6f} / ${budget.total:.2f})"
                )

            if not self.user_budget_exceeded.get(f"{user_id}_total") and usage_pct >= 1.0:
                self.user_budget_exceeded[f"{user_id}_total"] = True
                logger.error(
                    f"User {user_id}: Total budget exceeded! "
                    f"${user_cost:.6f} / ${budget.total:.2f}"
                )

    def get_user_summary(
        self,
        user_id: str,
        user_tier: Optional[str] = None
    ) -> dict[str, Any]:
        """
        NEW: Get cost summary for a specific user.

        Args:
            user_id: User ID
            user_tier: Optional tier for budget lookup

        Returns:
            Dict with user cost, budget, and usage information

        Example:
            >>> summary = tracker.get_user_summary('user_123', user_tier='free')
            >>> print(f"Cost: ${summary['total_cost']:.6f}")
            >>> print(f"Budget remaining: ${summary['budget_remaining']:.6f}")
            >>> print(f"Queries: {summary['total_queries']}")
        """
        user_cost = self.by_user.get(user_id, 0.0)
        user_entry_list = self.user_entries.get(user_id, [])

        summary = {
            "user_id": user_id,
            "total_cost": user_cost,
            "total_queries": len(user_entry_list),
            "has_budget": False,
        }

        # Get budget (user-specific or tier-based)
        budget = self.user_budgets.get(user_id)
        if not budget and user_tier:
            budget = self.user_budgets.get(user_tier)

        if budget and budget.has_any_limit():
            summary["has_budget"] = True
            summary["budget"] = budget

            # Daily budget info
            if budget.daily:
                summary["budget_daily"] = budget.daily
                summary["budget_remaining_daily"] = max(0, budget.daily - user_cost)
                summary["budget_used_pct_daily"] = (user_cost / budget.daily) * 100
                summary["budget_exceeded_daily"] = user_cost >= budget.daily

            # Total budget info
            if budget.total:
                summary["budget_total"] = budget.total
                summary["budget_remaining_total"] = max(0, budget.total - user_cost)
                summary["budget_used_pct_total"] = (user_cost / budget.total) * 100
                summary["budget_exceeded_total"] = user_cost >= budget.total

        return summary

    def get_users_by_tier(self, tier: str) -> list[str]:
        """
        NEW: Get all user IDs that have been tracked with a specific tier.

        Args:
            tier: Tier name (e.g., 'free', 'pro', 'enterprise')

        Returns:
            List of user IDs

        Example:
            >>> free_users = tracker.get_users_by_tier('free')
            >>> print(f"Free tier users: {len(free_users)}")
        """
        users = set()
        for user_id, entries in self.user_entries.items():
            for entry in entries:
                if entry.metadata.get('user_tier') == tier:
                    users.add(user_id)
                    break
        return sorted(users)

    def get_all_users(self) -> list[str]:
        """
        NEW: Get all user IDs that have been tracked.

        Returns:
            List of user IDs sorted alphabetically

        Example:
            >>> all_users = tracker.get_all_users()
            >>> print(f"Total users: {len(all_users)}")
        """
        return sorted(self.by_user.keys())
```

---

## 🧪 Test Plan

### Unit Tests (test_cost_tracker.py)

```python
import pytest
from cascadeflow.telemetry import CostTracker, BudgetConfig

def test_budget_config_creation():
    """Test BudgetConfig creation."""
    # Daily only
    budget = BudgetConfig(daily=0.10)
    assert budget.daily == 0.10
    assert budget.has_any_limit()

    # Multiple periods
    budget = BudgetConfig(daily=1.00, weekly=5.00, monthly=20.00)
    assert budget.daily == 1.00
    assert budget.has_any_limit()

    # No limits
    budget = BudgetConfig()
    assert not budget.has_any_limit()

def test_cost_tracker_backward_compatibility():
    """Test v0.1.1 usage still works."""
    tracker = CostTracker(budget_limit=10.0)

    # Add cost without user_id (v0.1.1 style)
    tracker.add_cost('gpt-4', 'openai', 100, 0.003)

    summary = tracker.get_summary()
    assert summary['total_cost'] == 0.003
    assert summary['total_entries'] == 1

def test_per_user_tracking_basic():
    """Test basic per-user cost tracking."""
    tracker = CostTracker(user_budgets={
        'free': BudgetConfig(daily=0.10),
        'pro': BudgetConfig(daily=1.00),
    })

    # Track costs for two users
    tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id='user_1', user_tier='free')
    tracker.add_cost('gpt-4', 'openai', 200, 0.006, user_id='user_2', user_tier='pro')
    tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id='user_1', user_tier='free')

    # Check user 1 summary
    summary1 = tracker.get_user_summary('user_1', user_tier='free')
    assert summary1['total_cost'] == 0.006  # 0.003 + 0.003
    assert summary1['total_queries'] == 2
    assert summary1['budget_daily'] == 0.10
    assert summary1['budget_remaining_daily'] == pytest.approx(0.094)

    # Check user 2 summary
    summary2 = tracker.get_user_summary('user_2', user_tier='pro')
    assert summary2['total_cost'] == 0.006
    assert summary2['total_queries'] == 1
    assert summary2['budget_daily'] == 1.00
    assert summary2['budget_remaining_daily'] == pytest.approx(0.994)

def test_budget_warning_threshold():
    """Test budget warning at 80% threshold."""
    tracker = CostTracker(user_budgets={
        'free': BudgetConfig(daily=0.10)
    })

    # Add costs up to 70% (no warning)
    tracker.add_cost('gpt-4', 'openai', 100, 0.070, user_id='user_1', user_tier='free')
    assert not tracker.user_budget_warned['user_1']

    # Add cost to reach 85% (warning)
    tracker.add_cost('gpt-4', 'openai', 100, 0.015, user_id='user_1', user_tier='free')
    assert tracker.user_budget_warned['user_1']
    assert not tracker.user_budget_exceeded['user_1']

def test_budget_exceeded():
    """Test budget exceeded alert."""
    tracker = CostTracker(user_budgets={
        'free': BudgetConfig(daily=0.10)
    })

    # Add costs to exceed budget
    tracker.add_cost('gpt-4', 'openai', 100, 0.12, user_id='user_1', user_tier='free')

    assert tracker.user_budget_warned['user_1']
    assert tracker.user_budget_exceeded['user_1']

    summary = tracker.get_user_summary('user_1', user_tier='free')
    assert summary['budget_exceeded_daily']
    assert summary['budget_remaining_daily'] == 0.0

def test_get_users_by_tier():
    """Test getting users by tier."""
    tracker = CostTracker()

    tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id='user_1', user_tier='free')
    tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id='user_2', user_tier='free')
    tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id='user_3', user_tier='pro')

    free_users = tracker.get_users_by_tier('free')
    assert len(free_users) == 2
    assert 'user_1' in free_users
    assert 'user_2' in free_users

    pro_users = tracker.get_users_by_tier('pro')
    assert len(pro_users) == 1
    assert 'user_3' in pro_users

def test_get_all_users():
    """Test getting all tracked users."""
    tracker = CostTracker()

    tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id='user_1')
    tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id='user_2')
    tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id='user_3')

    all_users = tracker.get_all_users()
    assert len(all_users) == 3
    assert all_users == ['user_1', 'user_2', 'user_3']  # Sorted

def test_user_specific_vs_tier_budget():
    """Test user-specific budget takes precedence over tier budget."""
    tracker = CostTracker(user_budgets={
        'free': BudgetConfig(daily=0.10),  # Tier budget
        'user_vip': BudgetConfig(daily=5.00),  # User-specific budget
    })

    # Regular free user uses tier budget
    tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id='user_1', user_tier='free')
    summary1 = tracker.get_user_summary('user_1', user_tier='free')
    assert summary1['budget_daily'] == 0.10

    # VIP user uses user-specific budget
    tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id='user_vip', user_tier='free')
    summary2 = tracker.get_user_summary('user_vip', user_tier='free')
    assert summary2['budget_daily'] == 5.00  # User-specific, not tier

def test_performance_many_users():
    """Test performance with many users (100 users, 1000 queries)."""
    import time

    tracker = CostTracker(user_budgets={
        'free': BudgetConfig(daily=0.10)
    })

    start = time.time()

    # Add 1000 cost entries for 100 users
    for i in range(1000):
        user_id = f"user_{i % 100}"
        tracker.add_cost('gpt-4', 'openai', 100, 0.003, user_id=user_id, user_tier='free')

    elapsed = time.time() - start

    # Should take <100ms for 1000 entries
    assert elapsed < 0.1, f"Performance issue: {elapsed:.3f}s for 1000 entries"

    # Verify tracking
    assert len(tracker.get_all_users()) == 100
    assert tracker.total_cost == pytest.approx(3.0)  # 1000 × 0.003
```

---

## 📊 Real-World Validation

### Scenario 1: Sarah's SaaS (Free + Pro Tiers)

```python
# Sarah's backend (Node.js/TypeScript uses Python API via HTTP)
from cascadeflow.telemetry import CostTracker, BudgetConfig

# Initialize with tier budgets
tracker = CostTracker(user_budgets={
    'free': BudgetConfig(daily=0.10),   # $0.10/day for free users
    'pro': BudgetConfig(daily=1.00),    # $1/day for pro users
})

# Track costs for users
def handle_ai_query(user_id: str, user_subscription: str, query: str):
    # ... call AI model ...

    # Track cost with user context
    tracker.add_cost(
        model='gpt-4',
        provider='openai',
        tokens=response.usage.total_tokens,
        cost=calculate_cost(response),
        user_id=user_id,
        user_tier=user_subscription  # 'free' or 'pro'
    )

    # Check if user exceeded budget
    summary = tracker.get_user_summary(user_id, user_tier=user_subscription)
    if summary.get('budget_exceeded_daily'):
        # Show upgrade prompt to user
        return {
            'response': response.text,
            'budget_exceeded': True,
            'message': 'Daily AI query limit reached. Upgrade to Pro for more!'
        }

    return {'response': response.text}

# Monitor free tier users
free_users = tracker.get_users_by_tier('free')
print(f"Free tier users today: {len(free_users)}")

for user_id in free_users:
    summary = tracker.get_user_summary(user_id, user_tier='free')
    if summary['budget_used_pct_daily'] > 50:
        # Send email: "You've used 50% of your daily AI queries!"
        send_upgrade_email(user_id)
```

**Benefit:** Sarah can now enforce per-user budgets with 10 lines of code

### Scenario 2: Code Tool (Per-User Tracking, No Budgets)

```python
# Track costs per user but don't enforce budgets yet
tracker = CostTracker()  # No budgets

# Just track who's using how much
tracker.add_cost('deepseek-coder', 'deepseek', 1000, 0.0014, user_id='dev_123')
tracker.add_cost('gpt-4', 'openai', 500, 0.015, user_id='dev_123')

# Generate invoice at end of month
all_users = tracker.get_all_users()
for user_id in all_users:
    summary = tracker.get_user_summary(user_id)
    print(f"Invoice for {user_id}: ${summary['total_cost']:.2f}")
```

**Benefit:** Can track usage without enforcing limits (useful for invoicing)

---

## ✅ Validation Checklist

Before implementing, validate this design:

### API Design
- [ ] Is the API intuitive? (Can developer understand in 5 minutes?)
- [ ] Is it backward compatible? (v0.1.1 code still works?)
- [ ] Is the naming clear? (`BudgetConfig`, `user_budgets`, `get_user_summary`)
- [ ] Are the examples realistic? (Sarah's SaaS, code tool)

### Real-World Benefit
- [ ] Does it solve Sarah's problem? (Enforce free tier budgets)
- [ ] Is it flexible enough? (Works with Stripe, Auth0, custom systems)
- [ ] Is it simple enough? (10 lines of code to add to existing app)

### Production Readiness
- [ ] Is it performant? (<1ms per add_cost call)
- [ ] Is it memory efficient? (O(users) space)
- [ ] Is it testable? (100% coverage possible)
- [ ] Are error messages clear?

### Missing Features (Deferred to Later Milestones)
- [ ] Time-based budget resets (daily/weekly/monthly) → Milestone 1.2
- [ ] Budget enforcement callbacks → Milestone 1.2
- [ ] Graceful degradation → Milestone 1.3
- [ ] Cost forecasting → Phase 2
- [ ] Anomaly detection → Phase 2

---

## 🚦 Decision: Ready to Implement?

**Status:** ⏸️ Awaiting validation from user

**Questions for User:**
1. Is the API design intuitive and clear?
2. Does `BudgetConfig` have the right fields? (daily/weekly/monthly/total)
3. Should we support time-based resets in this milestone, or defer to 1.2?
4. Any concerns about performance or complexity?

**If approved:** Move to implementation
**If changes needed:** Update design and re-validate
