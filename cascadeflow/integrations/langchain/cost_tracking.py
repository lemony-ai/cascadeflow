"""Cost tracking utilities for CascadeFlow LangChain integration.

Python-specific features for budget tracking, cost analysis, and reporting.

Features that TypeScript doesn't have:
- Budget tracking with warnings
- Cost history analysis
- CSV/Pandas DataFrame export
- Context managers for automatic cost reporting
- Decorators for cost tracking
"""

import csv
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional, TypeVar

from .types import CascadeResult

try:
    import pandas as pd  # type: ignore

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


@dataclass
class CostEntry:
    """Single cost tracking entry."""

    timestamp: datetime
    query: str
    model_used: str
    drafter_cost: float
    verifier_cost: float
    total_cost: float
    savings_percentage: float
    accepted: bool
    drafter_quality: float
    latency_ms: float


@dataclass
class BudgetTracker:
    """Track costs against a budget with warnings.

    Example:
        >>> tracker = BudgetTracker(budget=1.00)  # $1 budget
        >>> tracker.add_cost(0.0005, "gpt-4o-mini")
        >>> tracker.add_cost(0.05, "gpt-4o")
        >>> if tracker.is_over_budget():
        ...     print(tracker.get_warning())
    """

    budget: float
    spent: float = 0.0
    entries: list[dict[str, Any]] = field(default_factory=list)
    warning_threshold: float = 0.8  # Warn at 80% of budget

    def add_cost(self, cost: float, model: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Add cost entry and track spending."""
        self.spent += cost
        entry = {
            "timestamp": datetime.now(),
            "model": model,
            "cost": cost,
            "total_spent": self.spent,
            "metadata": metadata or {},
        }
        self.entries.append(entry)

    def is_over_budget(self) -> bool:
        """Check if over budget."""
        return self.spent > self.budget

    def is_near_budget(self) -> bool:
        """Check if near budget threshold."""
        return self.spent >= (self.budget * self.warning_threshold)

    def get_remaining(self) -> float:
        """Get remaining budget."""
        return max(0.0, self.budget - self.spent)

    def get_warning(self) -> Optional[str]:
        """Get budget warning if applicable."""
        if self.is_over_budget():
            overage = self.spent - self.budget
            return (
                f"⚠️  BUDGET EXCEEDED: Spent ${self.spent:.4f} (budget: ${self.budget:.4f}), "
                f"over by ${overage:.4f}"
            )
        elif self.is_near_budget():
            remaining = self.get_remaining()
            return (
                f"⚠️  BUDGET WARNING: Spent ${self.spent:.4f} of ${self.budget:.4f} "
                f"({(self.spent/self.budget*100):.1f}%), ${remaining:.4f} remaining"
            )
        return None

    def get_summary(self) -> dict[str, Any]:
        """Get budget summary."""
        return {
            "budget": self.budget,
            "spent": self.spent,
            "remaining": self.get_remaining(),
            "percent_used": (self.spent / self.budget * 100) if self.budget > 0 else 0,
            "over_budget": self.is_over_budget(),
            "total_calls": len(self.entries),
        }

    def reset(self) -> None:
        """Reset tracking."""
        self.spent = 0.0
        self.entries.clear()


@dataclass
class CostHistory:
    """Track and analyze cascade cost history.

    Example:
        >>> history = CostHistory()
        >>> result = cascade.get_last_cascade_result()
        >>> history.add_result(result, "What is 2+2?")
        >>> print(history.get_summary())
        >>> history.export_csv("costs.csv")
    """

    entries: list[CostEntry] = field(default_factory=list)

    def add_result(self, result: CascadeResult, query: str = "") -> None:
        """Add cascade result to history."""
        entry = CostEntry(
            timestamp=datetime.now(),
            query=query[:100],  # Truncate long queries
            model_used=result["model_used"],
            drafter_cost=result["drafter_cost"],
            verifier_cost=result["verifier_cost"],
            total_cost=result["total_cost"],
            savings_percentage=result["savings_percentage"],
            accepted=result["accepted"],
            drafter_quality=result["drafter_quality"],
            latency_ms=result["latency_ms"],
        )
        self.entries.append(entry)

    def get_total_cost(self) -> float:
        """Get total cost across all entries."""
        return sum(e.total_cost for e in self.entries)

    def get_avg_savings(self) -> float:
        """Get average savings percentage."""
        if not self.entries:
            return 0.0
        return sum(e.savings_percentage for e in self.entries) / len(self.entries)

    def get_acceptance_rate(self) -> float:
        """Get drafter acceptance rate."""
        if not self.entries:
            return 0.0
        accepted = sum(1 for e in self.entries if e.accepted)
        return (accepted / len(self.entries)) * 100

    def get_summary(self) -> dict[str, Any]:
        """Get cost history summary."""
        if not self.entries:
            return {
                "total_queries": 0,
                "total_cost": 0.0,
                "avg_cost": 0.0,
                "avg_savings": 0.0,
                "acceptance_rate": 0.0,
                "total_drafter_cost": 0.0,
                "total_verifier_cost": 0.0,
            }

        return {
            "total_queries": len(self.entries),
            "total_cost": self.get_total_cost(),
            "avg_cost": self.get_total_cost() / len(self.entries),
            "avg_savings": self.get_avg_savings(),
            "acceptance_rate": self.get_acceptance_rate(),
            "total_drafter_cost": sum(e.drafter_cost for e in self.entries),
            "total_verifier_cost": sum(e.verifier_cost for e in self.entries),
            "avg_latency_ms": sum(e.latency_ms for e in self.entries) / len(self.entries),
        }

    def export_csv(self, filename: str) -> None:
        """Export cost history to CSV."""
        if not self.entries:
            print("No cost data to export")
            return

        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "query",
                    "model_used",
                    "drafter_cost",
                    "verifier_cost",
                    "total_cost",
                    "savings_%",
                    "accepted",
                    "quality",
                    "latency_ms",
                ]
            )
            for entry in self.entries:
                writer.writerow(
                    [
                        entry.timestamp.isoformat(),
                        entry.query,
                        entry.model_used,
                        f"{entry.drafter_cost:.6f}",
                        f"{entry.verifier_cost:.6f}",
                        f"{entry.total_cost:.6f}",
                        f"{entry.savings_percentage:.2f}",
                        entry.accepted,
                        f"{entry.drafter_quality:.2f}",
                        f"{entry.latency_ms:.0f}",
                    ]
                )

        print(f"✅ Exported {len(self.entries)} entries to {filename}")

    def to_dataframe(self):
        """Export to pandas DataFrame (if pandas is installed).

        Returns:
            pandas.DataFrame with cost history

        Raises:
            ImportError: If pandas is not installed
        """
        if not HAS_PANDAS:
            raise ImportError(
                "pandas is required for DataFrame export. Install with: pip install pandas"
            )

        if not self.entries:
            return pd.DataFrame()

        data = [
            {
                "timestamp": e.timestamp,
                "query": e.query,
                "model_used": e.model_used,
                "drafter_cost": e.drafter_cost,
                "verifier_cost": e.verifier_cost,
                "total_cost": e.total_cost,
                "savings_percentage": e.savings_percentage,
                "accepted": e.accepted,
                "drafter_quality": e.drafter_quality,
                "latency_ms": e.latency_ms,
            }
            for e in self.entries
        ]

        return pd.DataFrame(data)

    def print_report(self) -> None:
        """Print formatted cost report."""
        summary = self.get_summary()

        print("\n" + "=" * 80)
        print("CASCADE COST REPORT")
        print("=" * 80)
        print(f"Total Queries:     {summary['total_queries']}")
        print(f"Total Cost:        ${summary['total_cost']:.6f}")
        print(f"Average Cost:      ${summary['avg_cost']:.6f}")
        print(f"Average Savings:   {summary['avg_savings']:.1f}%")
        print(f"Acceptance Rate:   {summary['acceptance_rate']:.1f}%")
        print(f"Average Latency:   {summary['avg_latency_ms']:.0f}ms")
        print()
        print("COST BREAKDOWN:")
        print(f"  Drafter Cost:    ${summary['total_drafter_cost']:.6f}")
        print(f"  Verifier Cost:   ${summary['total_verifier_cost']:.6f}")
        print("=" * 80 + "\n")


F = TypeVar("F", bound=Callable[..., Any])


@contextmanager
def track_costs(history: Optional[CostHistory] = None, budget: Optional[float] = None):
    """Context manager for automatic cost tracking.

    Example:
        >>> from cascadeflow.integrations.langchain import CascadeFlow, track_costs
        >>>
        >>> cascade = CascadeFlow(drafter=..., verifier=...)
        >>>
        >>> with track_costs(budget=1.00) as tracker:
        ...     result = await cascade.ainvoke("What is 2+2?")
        ...     tracker.add_result(result)
        ...
        >>> # Automatic cost report printed at end
    """
    cost_history = history or CostHistory()
    budget_tracker = BudgetTracker(budget=budget) if budget else None

    class Tracker:
        def add_result(self, result: CascadeResult, query: str = ""):
            cost_history.add_result(result, query)
            if budget_tracker:
                budget_tracker.add_cost(
                    result["total_cost"],
                    result["model_used"],
                    {"query": query, "accepted": result["accepted"]},
                )
                warning = budget_tracker.get_warning()
                if warning:
                    print(warning)

        def get_history(self) -> CostHistory:
            return cost_history

        def get_budget(self) -> Optional[BudgetTracker]:
            return budget_tracker

    try:
        yield Tracker()
    finally:
        # Print summary at end
        if cost_history.entries:
            cost_history.print_report()
        if budget_tracker and budget_tracker.entries:
            summary = budget_tracker.get_summary()
            print(
                f"\nBudget: ${summary['budget']:.4f} | "
                f"Spent: ${summary['spent']:.4f} | "
                f"Remaining: ${summary['remaining']:.4f}"
            )
