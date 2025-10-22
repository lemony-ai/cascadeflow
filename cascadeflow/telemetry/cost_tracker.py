"""
Cost tracking for CascadeFlow.

Tracks costs across queries, models, and providers for monitoring
and budget management.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


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
    ):
        """
        Initialize cost tracker.

        Args:
            budget_limit: Optional budget limit in dollars
            warn_threshold: Warn when cost reaches this % of budget
            verbose: Enable verbose logging
        """
        self.budget_limit = budget_limit
        self.warn_threshold = warn_threshold
        self.verbose = verbose

        # Cost tracking
        self.total_cost = 0.0
        self.by_model: dict[str, float] = defaultdict(float)
        self.by_provider: dict[str, float] = defaultdict(float)
        self.entries: list[CostEntry] = []

        # Budget alerts
        self.budget_warned = False
        self.budget_exceeded = False

        logger.info(
            f"CostTracker initialized: " f"budget_limit=${budget_limit if budget_limit else 'None'}"
        )

    def add_cost(
        self,
        model: str,
        provider: str,
        tokens: int,
        cost: float,
        query_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
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

        # Update totals
        self.total_cost += cost
        self.by_model[model] += cost
        self.by_provider[provider] += cost
        self.entries.append(entry)

        # Check budget
        self._check_budget()

        if self.verbose:
            logger.info(f"Added cost: {model} ({provider}), " f"{tokens} tokens, ${cost:.6f}")

    def _check_budget(self) -> None:
        """Check if budget limits have been reached."""
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

    def reset(self) -> None:
        """Reset all cost tracking."""
        self.total_cost = 0.0
        self.by_model.clear()
        self.by_provider.clear()
        self.entries.clear()
        self.budget_warned = False
        self.budget_exceeded = False
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


__all__ = ["CostTracker", "CostEntry"]
