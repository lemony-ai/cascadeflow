"""
Cost tracking for cascadeflow.

Tracks costs across queries, models, and providers for monitoring
and budget management.

NEW in v0.2.0:
    - Per-user cost tracking
    - Per-user budget enforcement (daily/weekly/monthly/total)
    - Time-based budget resets
    - Backward compatible with v0.1.1
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BudgetConfig:
    """
    Per-user/tier budget configuration (NEW in v0.2.0).

    Supports multiple budget periods with automatic time-based resets.
    Only specify the periods you need. If no budget is specified,
    tracking still happens but no limits are enforced.

    Examples:
        >>> # Daily budget only (most common for SaaS)
        >>> free_tier = BudgetConfig(daily=0.10)
        >>>
        >>> # Multiple periods for comprehensive control
        >>> pro_tier = BudgetConfig(
        ...     daily=1.00,
        ...     weekly=5.00,
        ...     monthly=20.00
        ... )
        >>>
        >>> # Total lifetime budget (for trials)
        >>> trial = BudgetConfig(total=5.00)
    """

    daily: Optional[float] = None  # Daily budget in USD
    weekly: Optional[float] = None  # Weekly budget in USD (Mon-Sun)
    monthly: Optional[float] = None  # Monthly budget in USD
    total: Optional[float] = None  # Total lifetime budget in USD

    def has_any_limit(self) -> bool:
        """Check if any budget limit is set."""
        return any([self.daily, self.weekly, self.monthly, self.total])

    def __repr__(self) -> str:
        """Human-readable representation."""
        limits = []
        if self.daily:
            limits.append(f"daily=${self.daily:.2f}")
        if self.weekly:
            limits.append(f"weekly=${self.weekly:.2f}")
        if self.monthly:
            limits.append(f"monthly=${self.monthly:.2f}")
        if self.total:
            limits.append(f"total=${self.total:.2f}")

        if not limits:
            return "BudgetConfig(no limits)"
        return f"BudgetConfig({', '.join(limits)})"


@dataclass
class CostEntry:
    """Single cost entry."""

    timestamp: datetime
    model: str
    provider: str
    tokens: int
    cost: float
    query_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CostTracker:
    """
    Track costs across queries and models.

    Features:
    - Per-model cost tracking
    - Per-provider cost tracking
    - Budget alerts
    - Cost history

    Usage:
        tracker = CostTracker(budget_limit=10.0)
        tracker.add_cost(model='gpt-4', tokens=100, cost=0.003)

        summary = tracker.get_summary()
        print(f"Total cost: ${summary['total_cost']:.6f}")
    """

    def __init__(
        self,
        budget_limit: Optional[float] = None,
        warn_threshold: float = 0.8,
        verbose: bool = False,
        user_budgets: Optional[dict[str, BudgetConfig]] = None,
        enforcement_mode: str = "warn",
    ):
        """
        Initialize cost tracker.

        Args:
            budget_limit: Optional global budget limit in dollars (backward compatible)
            warn_threshold: Warn when cost reaches this % of budget
            verbose: Enable verbose logging
            user_budgets: Optional per-user budget configs (NEW in v0.2.0)
            enforcement_mode: Enforcement mode - 'warn', 'block', or 'degrade' (NEW in v0.2.0)

        Example:
            >>> # v0.1.1 style (backward compatible)
            >>> tracker = CostTracker(budget_limit=10.0)
            >>>
            >>> # v0.2.0 style with per-user budgets
            >>> tracker = CostTracker(
            ...     user_budgets={
            ...         'free': BudgetConfig(daily=0.10),
            ...         'pro': BudgetConfig(daily=1.00, weekly=5.00)
            ...     }
            ... )
        """
        # Validate enforcement_mode
        valid_modes = ("warn", "block", "degrade")
        if enforcement_mode not in valid_modes:
            raise ValueError(
                f"Invalid enforcement_mode: {enforcement_mode}. Must be one of {valid_modes}"
            )

        self.budget_limit = budget_limit
        self.warn_threshold = warn_threshold
        self.verbose = verbose
        self.enforcement_mode = enforcement_mode

        # Cost tracking (v0.1.1 - backward compatible)
        self.total_cost = 0.0
        self.by_model: dict[str, float] = defaultdict(float)
        self.by_provider: dict[str, float] = defaultdict(float)
        self.entries: list[CostEntry] = []

        # Budget alerts (v0.1.1 - backward compatible)
        self.budget_warned = False
        self.budget_exceeded = False

        # NEW v0.2.0: Per-user tracking
        self.user_budgets = user_budgets or {}
        self.by_user: dict[str, float] = defaultdict(float)
        self.user_entries: dict[str, list[CostEntry]] = defaultdict(list)
        self.user_budget_warned: dict[str, set[str]] = defaultdict(
            set
        )  # user_id -> set of warned periods
        self.user_budget_exceeded: dict[str, set[str]] = defaultdict(
            set
        )  # user_id -> set of exceeded periods
        self.user_period_start: dict[str, dict[str, datetime]] = defaultdict(
            dict
        )  # user_id -> period -> start_time

        logger.info(
            f"CostTracker initialized: "
            f"budget_limit=${budget_limit if budget_limit else 'None'}, "
            f"user_budgets={len(self.user_budgets)} tiers"
        )

    def add_cost(
        self,
        model: str,
        provider: str,
        tokens: int,
        cost: float,
        query_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
        user_tier: Optional[str] = None,
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
            user_id: Optional user identifier (NEW in v0.2.0)
            user_tier: Optional user tier name (NEW in v0.2.0)

        Example:
            >>> # v0.1.1 style (backward compatible)
            >>> tracker.add_cost(model='gpt-4', provider='openai', tokens=100, cost=0.003)
            >>>
            >>> # v0.2.0 style with user tracking
            >>> tracker.add_cost(
            ...     model='gpt-4', provider='openai', tokens=100, cost=0.003,
            ...     user_id='user_123', user_tier='free'
            ... )
        """
        # Create entry
        entry = CostEntry(
            timestamp=datetime.now(),
            model=model,
            provider=provider,
            tokens=tokens,
            cost=cost,
            query_id=query_id,
            metadata=metadata or {},
        )

        # Update global totals (v0.1.1 - backward compatible)
        self.total_cost += cost
        self.by_model[model] += cost
        self.by_provider[provider] += cost
        self.entries.append(entry)

        # NEW v0.2.0: Update per-user tracking
        if user_id is not None:  # Allow empty string
            self.by_user[user_id] += cost
            self.user_entries[user_id].append(entry)

        # Check global budget (v0.1.1 - backward compatible)
        self._check_budget()

        # NEW v0.2.0: Check per-user budget
        if user_id and user_tier:
            self._check_user_budget(user_id, user_tier, cost)

        if self.verbose:
            user_info = f", user={user_id}:{user_tier}" if user_id else ""
            logger.info(
                f"Added cost: {model} ({provider}), {tokens} tokens, ${cost:.6f}{user_info}"
            )

    def _check_budget(self) -> None:
        """Check if global budget limits have been reached (v0.1.1 - backward compatible)."""
        if not self.budget_limit:
            return

        usage_pct = self.total_cost / self.budget_limit

        # Warn at threshold
        if not self.budget_warned and usage_pct >= self.warn_threshold:
            self.budget_warned = True
            logger.warning(
                f"Cost tracker: {usage_pct*100:.1f}% of budget used "
                f"(${self.total_cost:.6f} / ${self.budget_limit:.2f})"
            )

        # Alert when exceeded
        if not self.budget_exceeded and usage_pct >= 1.0:
            self.budget_exceeded = True
            logger.error(
                f"Cost tracker: Budget exceeded! "
                f"${self.total_cost:.6f} / ${self.budget_limit:.2f}"
            )

    def _check_user_budget(self, user_id: str, user_tier: str, cost: float) -> None:
        """
        Check if per-user budget limits have been reached (NEW in v0.2.0).

        Supports time-based budget resets for daily/weekly/monthly periods.

        Args:
            user_id: User identifier
            user_tier: User tier name (must exist in self.user_budgets)
            cost: Cost being added
        """
        # Get budget config for this tier
        budget_config = self.user_budgets.get(user_tier)
        if not budget_config or not budget_config.has_any_limit():
            return  # No budget limits configured for this tier

        # Use the latest entry timestamp (more accurate than datetime.now())
        if user_id in self.user_entries and len(self.user_entries[user_id]) > 0:
            now = self.user_entries[user_id][-1].timestamp
        else:
            now = datetime.now()

        # Check each budget period
        periods_to_check = []
        if budget_config.daily is not None:
            periods_to_check.append(("daily", budget_config.daily, timedelta(days=1)))
        if budget_config.weekly is not None:
            periods_to_check.append(("weekly", budget_config.weekly, timedelta(weeks=1)))
        if budget_config.monthly is not None:
            periods_to_check.append(("monthly", budget_config.monthly, timedelta(days=30)))
        if budget_config.total is not None:
            periods_to_check.append(("total", budget_config.total, None))

        for period_name, limit, reset_delta in periods_to_check:
            # Get period start time
            if user_id not in self.user_period_start:
                self.user_period_start[user_id] = {}

            if period_name not in self.user_period_start[user_id]:
                # First cost for this user/period
                self.user_period_start[user_id][period_name] = now

            period_start = self.user_period_start[user_id][period_name]

            # Check if period should reset
            if reset_delta is not None and (now - period_start) >= reset_delta:
                # Reset period
                self._reset_user_period(user_id, period_name)
                self.user_period_start[user_id][period_name] = now
                period_start = now

            # Calculate period cost
            period_cost = self._get_user_period_cost(
                user_id, period_start, now if reset_delta else None
            )

            # Check limits
            usage_pct = period_cost / limit

            # Warn at threshold
            period_key = f"{user_tier}:{period_name}"
            if (
                period_key not in self.user_budget_warned[user_id]
                and usage_pct >= self.warn_threshold
            ):
                self.user_budget_warned[user_id].add(period_key)
                logger.warning(
                    f"User {user_id} ({user_tier}): {usage_pct*100:.1f}% of {period_name} budget used "
                    f"(${period_cost:.6f} / ${limit:.2f})"
                )

            # Alert when exceeded
            if period_key not in self.user_budget_exceeded[user_id] and usage_pct >= 1.0:
                self.user_budget_exceeded[user_id].add(period_key)
                logger.error(
                    f"User {user_id} ({user_tier}): {period_name} budget exceeded! "
                    f"${period_cost:.6f} / ${limit:.2f}"
                )

    def _reset_user_period(self, user_id: str, period_name: str) -> None:
        """Reset budget warnings/exceeded flags for a user period."""
        # Remove warnings/exceeded for this period
        period_keys_to_remove = [
            k for k in self.user_budget_warned[user_id] if k.endswith(f":{period_name}")
        ]
        for key in period_keys_to_remove:
            self.user_budget_warned[user_id].discard(key)
            self.user_budget_exceeded[user_id].discard(key)

        if self.verbose:
            logger.info(f"Reset {period_name} budget period for user {user_id}")

    def _get_user_period_cost(
        self, user_id: str, period_start: datetime, period_end: Optional[datetime]
    ) -> float:
        """
        Calculate total cost for a user within a time period.

        Args:
            user_id: User identifier
            period_start: Period start time
            period_end: Period end time (None for total/lifetime)

        Returns:
            Total cost in dollars
        """
        if user_id not in self.user_entries:
            return 0.0

        total = 0.0
        for entry in self.user_entries[user_id]:
            if entry.timestamp >= period_start:
                if period_end is None or entry.timestamp <= period_end:
                    total += entry.cost

        return total

    def get_summary(self) -> dict[str, Any]:
        """
        Get cost summary.

        Returns:
            Dict with total cost, by model, by provider, etc.
        """
        summary = {
            "total_cost": self.total_cost,
            "total_entries": len(self.entries),
            "by_model": dict(self.by_model),
            "by_provider": dict(self.by_provider),
        }

        if self.budget_limit:
            summary["budget_limit"] = self.budget_limit
            summary["budget_remaining"] = max(0, self.budget_limit - self.total_cost)
            summary["budget_used_pct"] = (self.total_cost / self.budget_limit) * 100
            summary["budget_exceeded"] = self.budget_exceeded

        return summary

    def get_recent_entries(self, n: int = 10) -> list[CostEntry]:
        """Get n most recent cost entries."""
        return self.entries[-n:]

    def get_entries_by_model(self, model: str) -> list[CostEntry]:
        """Get all entries for a specific model."""
        return [e for e in self.entries if e.model == model]

    def get_entries_by_provider(self, provider: str) -> list[CostEntry]:
        """Get all entries for a specific provider."""
        return [e for e in self.entries if e.provider == provider]

    def get_user_summary(self, user_id: str, user_tier: Optional[str] = None) -> dict[str, Any]:
        """
        Get cost summary for a specific user (NEW in v0.2.0).

        Args:
            user_id: User identifier
            user_tier: Optional user tier name (for budget info)

        Returns:
            Dict with user's total cost, entries, budget status, etc.

        Example:
            >>> summary = tracker.get_user_summary('user_123', 'free')
            >>> print(f"User cost: ${summary['total_cost']:.6f}")
            >>> if summary['budget_exceeded']:
            ...     print("Budget exceeded!")
        """
        summary = {
            "user_id": user_id,
            "total_cost": self.by_user.get(user_id, 0.0),
            "total_entries": len(self.user_entries.get(user_id, [])),
        }

        # Add budget info if tier provided
        if user_tier and user_tier in self.user_budgets:
            budget_config = self.user_budgets[user_tier]
            summary["user_tier"] = user_tier
            summary["budget_config"] = str(budget_config)

            # Calculate period costs
            now = datetime.now()
            period_costs = {}

            for period_name in ["daily", "weekly", "monthly", "total"]:
                limit = getattr(budget_config, period_name)
                if limit is not None:
                    # Calculate period cost
                    if (
                        user_id in self.user_period_start
                        and period_name in self.user_period_start[user_id]
                    ):
                        # Period tracking exists - use it
                        period_start = self.user_period_start[user_id][period_name]
                        period_cost = self._get_user_period_cost(
                            user_id, period_start, now if period_name != "total" else None
                        )
                    elif user_id in self.user_entries and len(self.user_entries[user_id]) > 0:
                        # Period tracking doesn't exist yet, but user has entries
                        # Use earliest entry timestamp as period start
                        earliest_entry = min(self.user_entries[user_id], key=lambda e: e.timestamp)
                        period_start = earliest_entry.timestamp
                        period_cost = self._get_user_period_cost(
                            user_id, period_start, now if period_name != "total" else None
                        )
                    else:
                        # No entries yet - cost is 0
                        period_cost = 0.0

                    period_costs[period_name] = {
                        "cost": period_cost,
                        "limit": limit,
                        "remaining": max(0, limit - period_cost),
                        "used_pct": (period_cost / limit) * 100 if limit > 0 else 0,
                        "exceeded": period_cost >= limit,
                    }

            summary["period_costs"] = period_costs

            # Check if any budget exceeded
            period_key_prefix = f"{user_tier}:"
            summary["budget_exceeded"] = any(
                k.startswith(period_key_prefix)
                for k in self.user_budget_exceeded.get(user_id, set())
            )

        return summary

    def get_all_users(self) -> list[str]:
        """
        Get list of all tracked user IDs (NEW in v0.2.0).

        Returns:
            List of user IDs
        """
        return list(self.by_user.keys())

    def get_users_by_tier(self, tier: str) -> list[str]:
        """
        Get all users in a specific tier (NEW in v0.2.0).

        Note: This returns users who have been tracked with this tier.
        It doesn't track tier changes - if a user's tier changes,
        you need to manage that separately.

        Args:
            tier: Tier name

        Returns:
            List of user IDs that have costs tracked with this tier
        """
        users = []
        for user_id in self.by_user.keys():
            # Check if user has any warnings/exceeded for this tier
            tier_prefix = f"{tier}:"
            if any(k.startswith(tier_prefix) for k in self.user_budget_warned.get(user_id, set())):
                users.append(user_id)
            elif any(
                k.startswith(tier_prefix) for k in self.user_budget_exceeded.get(user_id, set())
            ):
                users.append(user_id)

        return users

    def can_afford(
        self, user_id: str, estimated_cost: float, user_tier: Optional[str] = None
    ) -> bool:
        """
        Check if user can afford estimated cost within their budget (NEW in v0.2.0).

        Args:
            user_id: User identifier
            estimated_cost: Estimated cost of the request in USD
            user_tier: Optional user tier name (required if using user_budgets)

        Returns:
            True if user can afford the cost, False otherwise

        Example:
            >>> tracker = CostTracker(user_budgets={"free": BudgetConfig(daily=0.10)})
            >>> tracker.add_cost(..., user_id="user_1", user_tier="free", cost=0.08)
            >>>
            >>> # Check if user can afford $0.03 more
            >>> if tracker.can_afford("user_1", 0.03, "free"):
            ...     print("Can afford")
            ... else:
            ...     print("Would exceed budget")
        """
        # If no user_tier provided or no budgets configured, allow
        if not user_tier or not self.user_budgets:
            return True

        # Get budget config for tier
        budget_config = self.user_budgets.get(user_tier)
        if not budget_config or not budget_config.has_any_limit():
            return True  # No limits, always allow

        # Get current user cost
        current_cost = self.by_user.get(user_id, 0.0)
        projected_cost = current_cost + estimated_cost

        # Check against daily budget (most common)
        if budget_config.daily is not None:
            # Get daily period cost
            if user_id in self.user_period_start and "daily" in self.user_period_start[user_id]:
                period_start = self.user_period_start[user_id]["daily"]
                from datetime import datetime

                period_cost = self._get_user_period_cost(user_id, period_start, datetime.now())
                projected_period_cost = period_cost + estimated_cost

                if projected_period_cost > budget_config.daily:
                    return False

        # Check against total budget if no daily budget
        elif budget_config.total is not None:
            if projected_cost > budget_config.total:
                return False

        return True

    def export_to_json(self, filepath: str) -> None:
        """
        Export cost tracking data to JSON file (NEW in v0.2.0).

        Args:
            filepath: Path to JSON file

        Example:
            >>> tracker.export_to_json("costs.json")
        """
        import json

        data = {
            "metadata": {
                "budget_limit": self.budget_limit,
                "enforcement_mode": self.enforcement_mode,
                "total_cost": self.total_cost,
                "total_entries": len(self.entries),
            },
            "by_model": dict(self.by_model),
            "by_provider": dict(self.by_provider),
            "by_user": dict(self.by_user),
            "entries": [
                {
                    "timestamp": entry.timestamp.isoformat(),
                    "model": entry.model,
                    "provider": entry.provider,
                    "tokens": entry.tokens,
                    "cost": entry.cost,
                    "query_id": entry.query_id,
                    "metadata": entry.metadata,
                }
                for entry in self.entries
            ],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(self.entries)} entries to {filepath}")

    def export_to_csv(self, filepath: str) -> None:
        """
        Export cost tracking data to CSV file (NEW in v0.2.0).

        Args:
            filepath: Path to CSV file

        Example:
            >>> tracker.export_to_csv("costs.csv")
        """
        import csv

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(
                [
                    "timestamp",
                    "model",
                    "provider",
                    "tokens",
                    "cost",
                    "query_id",
                    "metadata",
                ]
            )

            # Rows
            for entry in self.entries:
                writer.writerow(
                    [
                        entry.timestamp.isoformat(),
                        entry.model,
                        entry.provider,
                        entry.tokens,
                        entry.cost,
                        entry.query_id or "",
                        str(entry.metadata) if entry.metadata else "",
                    ]
                )

        logger.info(f"Exported {len(self.entries)} entries to {filepath}")

    def export_to_sqlite(self, filepath: str) -> None:
        """
        Export cost tracking data to SQLite database (NEW in v0.2.0).

        Creates a 'cost_entries' table with all cost data.

        Args:
            filepath: Path to SQLite database file

        Example:
            >>> tracker.export_to_sqlite("costs.db")
        """
        import json
        import sqlite3

        conn = sqlite3.connect(filepath)
        cursor = conn.cursor()

        # Create table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cost_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                model TEXT NOT NULL,
                provider TEXT NOT NULL,
                tokens INTEGER,
                cost REAL NOT NULL,
                query_id TEXT,
                metadata TEXT
            )
        """
        )

        # Insert entries
        for entry in self.entries:
            cursor.execute(
                """
                INSERT INTO cost_entries (timestamp, model, provider, tokens, cost, query_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entry.timestamp.isoformat(),
                    entry.model,
                    entry.provider,
                    entry.tokens,
                    entry.cost,
                    entry.query_id,
                    json.dumps(entry.metadata) if entry.metadata else None,
                ),
            )

        conn.commit()
        conn.close()

        logger.info(f"Exported {len(self.entries)} entries to {filepath}")

    def reset(self) -> None:
        """Reset all cost tracking (v0.1.1 - backward compatible)."""
        # Reset global tracking
        self.total_cost = 0.0
        self.by_model.clear()
        self.by_provider.clear()
        self.entries.clear()
        self.budget_warned = False
        self.budget_exceeded = False

        # NEW v0.2.0: Reset per-user tracking
        self.by_user.clear()
        self.user_entries.clear()
        self.user_budget_warned.clear()
        self.user_budget_exceeded.clear()
        self.user_period_start.clear()

        logger.info("Cost tracker reset")

    def print_summary(self) -> None:
        """Print formatted cost summary."""
        summary = self.get_summary()

        print("\n" + "=" * 60)
        print("COST TRACKER SUMMARY")
        print("=" * 60)
        print(f"Total Cost:        ${summary['total_cost']:.6f}")
        print(f"Total Entries:     {summary['total_entries']}")

        if self.budget_limit:
            print(f"Budget Limit:      ${summary['budget_limit']:.2f}")
            print(f"Budget Remaining:  ${summary['budget_remaining']:.6f}")
            print(f"Budget Used:       {summary['budget_used_pct']:.1f}%")
            if summary["budget_exceeded"]:
                print("⚠️  BUDGET EXCEEDED")

        print()
        print("BY MODEL:")
        for model, cost in sorted(summary["by_model"].items(), key=lambda x: x[1], reverse=True):
            pct = (cost / summary["total_cost"]) * 100 if summary["total_cost"] > 0 else 0
            print(f"  {model:30s}: ${cost:8.6f} ({pct:5.1f}%)")

        print()
        print("BY PROVIDER:")
        for provider, cost in sorted(
            summary["by_provider"].items(), key=lambda x: x[1], reverse=True
        ):
            pct = (cost / summary["total_cost"]) * 100 if summary["total_cost"] > 0 else 0
            print(f"  {provider:30s}: ${cost:8.6f} ({pct:5.1f}%)")

        print("=" * 60 + "\n")


__all__ = ["CostTracker", "CostEntry", "BudgetConfig"]
